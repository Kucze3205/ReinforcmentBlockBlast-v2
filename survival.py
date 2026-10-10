"""
Polityka przeżycia: wiązka po całej tacce na bitboardach (64 bity, bit = y*8+x).

Liść (plansza po zagraniu tacki) jest oceniany kosztem: ryzyko, że następna tacka
będzie niegrywalna (próbne tacki + ważone multizbiory trudnych typów), plus tanie
cechy planszy (izolowane dziury, zapełnienie, kruche typy). Punkty to tylko remis.
"""
import itertools
import random

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
ROWS = [0xFF << (8 * r) for r in range(8)]
COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
NOT_COL0 = FULL & ~COLS[0]
NOT_COL7 = FULL & ~COLS[7]
ROWS_0_6 = FULL & ~ROWS[7]

PLACEMENTS = []  # PLACEMENTS[idx] = [(maska, x, y), ...]
for _p in PIECE_POOL:
    h, w = len(_p.shape), len(_p.shape[0])
    lst = []
    for y in range(8 - h + 1):
        for x in range(8 - w + 1):
            m = 0
            for dy, row in enumerate(_p.shape):
                for dx, c in enumerate(row):
                    if c:
                        m |= 1 << ((y + dy) * 8 + x + dx)
            lst.append((m, x, y))
    PLACEMENTS.append(lst)
PMASKS = [[m for m, _, _ in l] for l in PLACEMENTS]

NC = [bin(ms[0]).count('1') for ms in PMASKS]

# trudne typy: square3, corner5, beam5, rect23, diag3
HARD_TYPES = [7, 10, 4, 6, 12]


def clear(board):
    """Zwraca (plansza po czyszczeniu, liczba linii)."""
    bs = board.to_bytes(8, "little")
    c = bs[0] & bs[1] & bs[2] & bs[3] & bs[4] & bs[5] & bs[6] & bs[7]
    n = 0
    rm = 0
    if 255 in bs:
        for r in range(8):
            if bs[r] == 255:
                rm |= ROWS[r]
                n += 1
    if c:
        rm |= c * 0x0101010101010101
        n += bin(c).count("1")
    if not n:
        return board, 0
    return board & ~rm, n


def playable(board, tray):
    """Czy da się zagrać całą tackę (kolejność dowolna). tray: krotka indeksów póz."""
    for idx in tray:
        for m in PMASKS[idx]:
            if not board & m:
                break
        else:
            return False
    seen = set()

    def rec(b, rest):
        if not rest:
            return True
        key = (b, rest)
        if key in seen:
            return False
        seen.add(key)
        for i, idx in enumerate(rest):
            if i and idx in rest[:i]:
                continue
            nxt = rest[:i] + rest[i + 1:]
            for m in PMASKS[idx]:
                if not b & m:
                    nb, _ = clear(b | m)
                    if rec(nb, nxt):
                        return True
        return False

    return rec(board, tuple(tray))


def popcount(x):
    return bin(x).count("1")


class SurvivalPolicy:
    name = "survival"

    def __init__(self, beam=100, risk_cands=40, trays=12, risk_w=60.0, hard_w=400.0, frag_w=15.0, mob_w=1.4, seed=0):
        self.mob_w = mob_w
        self.beam = beam
        self.risk_cands = risk_cands
        self.trays = trays
        self.risk_w = risk_w
        self.hard_w = hard_w
        self.frag_w = frag_w
        self._seed = seed
        self._rcache = {}
        self._ccache = {}
        self.reset(0)

    def reset(self, game_seed):
        self.rng = random.Random(f"{self._seed}:{game_seed}")

    def _risk(self, board, samples, hard_sets):
        r = self._rcache.get(board)
        if r is not None:
            return r
        bad = sum(1 for tr in samples if not playable(board, tr))
        r = self.risk_w * bad / len(samples)
        hb = sum(w for w, tr in hard_sets if not playable(board, tr))
        r += self.hard_w * hb
        frag = 0
        for t in PIECE_TYPES:
            n = 0
            for idx in t:
                for m in PMASKS[idx]:
                    if not board & m:
                        n += 1
                        if n >= 2:
                            break
                if n >= 2:
                    break
            frag += 2 - n
        r += self.frag_w * frag
        r -= self.mob_w * sum(NC[i] for i, ms in enumerate(PMASKS) if any(not board & m for m in ms))
        self._rcache[board] = r
        return r

    def _cheap(self, board):
        v = self._ccache.get(board)
        if v is not None:
            return v
        empty = ~board & FULL
        bl = ((board << 1) & NOT_COL0) | COLS[0]
        br = ((board >> 1) & NOT_COL7) | COLS[7]
        bu = ((board << 8) & FULL) | ROWS[0]
        bd = (board >> 8) | ROWS[7]
        all4 = bl & br & bu & bd
        at3 = (bl & br & bu) | (bl & br & bd) | (bl & bu & bd) | (br & bu & bd)
        iso = popcount(empty & all4)
        pocket = popcount(empty & at3 & ~all4)
        trans = popcount((board ^ (board >> 1)) & NOT_COL7) + popcount((board ^ (board >> 8)) & ROWS_0_6)
        v = 8.0 * popcount(board) + 25.0 * iso + 35.0 * pocket + 8.0 * trans
        if len(self._ccache) > 200000:
            self._ccache.clear()
        self._ccache[board] = v
        return v

    def _sample_trays(self):
        return [
            tuple(sorted(self.rng.choice(self.rng.choice(PIECE_TYPES)) for _ in range(3)))
            for _ in range(self.trays)
        ]

    def _hard_sets(self):
        sets = []
        for _ in range(35):
            w = self.rng.choice([1, 3, 6])
            tr = tuple(sorted(self.rng.choice(PIECE_TYPES[self.rng.choice(HARD_TYPES)]) for _ in range(3)))
            sets.append((w, tr))
        s = sum(w for w, _ in sets)
        return [(w / s, tr) for w, tr in sets]

    def act(self, game, actions):
        board = 0
        for y in range(8):
            row = game.board.grid[y]
            for x in range(8):
                if row[x]:
                    board |= 1 << (y * 8 + x)
        rest = [(i, p.index) for i, p in enumerate(game.pieces) if p is not None]

        samples = self._sample_trays()
        hard_sets = self._hard_sets()
        self._rcache = {}

        results = {}  # plansza końcowa -> (linie, pierwsza akcja)
        for perm in set(itertools.permutations(rest)):
            states = {board: (0, None)}
            for slot, idx in perm:
                new = {}
                for b, (ln, first) in states.items():
                    for m, x, y in PLACEMENTS[idx]:
                        if b & m:
                            continue
                        nb, n = clear(b | m)
                        v = ln + 10.0 * n * n
                        old = new.get(nb)
                        if old is None or v > old[0]:
                            new[nb] = (v, first if first is not None else (slot, x, y))
                if not new:
                    break
                if len(new) > self.beam * 3:
                    ranked = sorted(new.items(), key=lambda kv: self._cheap(kv[0]) - kv[1][0])
                    new = dict(ranked[: self.beam * 3])
                states = new
            else:
                for b, (ln, first) in states.items():
                    old = results.get(b)
                    if old is None or ln > old[0]:
                        results[b] = (ln, first)
        if not results:
            return actions[0]
        cands = sorted(results.items(), key=lambda kv: self._cheap(kv[0]) - kv[1][0])[: self.risk_cands]
        best = None
        for b, (ln, first) in cands:
            sc = self._cheap(b) - ln + self._risk(b, samples, hard_sets)
            if b == 0:
                sc -= 500
            if best is None or sc < best[0]:
                best = (sc, first)
        return tuple(best[1])


def build(weights=None):
    return SurvivalPolicy()
