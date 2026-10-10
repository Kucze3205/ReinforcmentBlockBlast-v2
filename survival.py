"""
Polityka przeżycia: wiązka po klockach bieżącej tacki na bitboardach (bit = y*8+x),
ocena liści kosztem układu planszy i ryzykiem, że następna losowa tacka będzie niegrywalna.
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

M = (1 << 64) - 1
NOT_C0 = 0xFEFEFEFEFEFEFEFE
NOT_C7 = 0x7F7F7F7F7F7F7F7F
ONES_R = 0x0101010101010101
# trudne typy: belka 5, kwadrat 3, prostokąt 2x3, narożnik 5, belka 4
HARD_TYPES = [4, 7, 6, 10, 3]

POSES = []  # POSES[i] = lista (maska, x, y)
for _p in PIECE_POOL:
    h, w = len(_p.shape), len(_p.shape[0])
    base = 0
    for dy, row in enumerate(_p.shape):
        for dx, c in enumerate(row):
            if c:
                base |= 1 << (dy * 8 + dx)
    POSES.append([(base << (y * 8 + x), x, y)
                  for y in range(9 - h) for x in range(9 - w)])
TYPE_POSES = [[m for i in idx for m, _, _ in POSES[i]] for idx in PIECE_TYPES]


def clear(b):
    x = b & (b >> 1)
    x &= x >> 2
    x &= x >> 4
    rows = x & ONES_R
    t = b & (b >> 8)
    t &= t >> 16
    t &= t >> 32
    cols = t & 0xFF
    if not rows and not cols:
        return b, 0
    mask = (rows * 255) | (cols * ONES_R)
    n = rows.bit_count() + cols.bit_count()
    return b & ~mask, n


def cheap(b, lines):
    e = ~b & M
    nb = ((e << 1) & NOT_C0) | ((e >> 1) & NOT_C7) | (e << 8) | (e >> 8)
    iso = (e & ~nb & M).bit_count()
    rough = ((b ^ (b >> 1)) & NOT_C7).bit_count() + ((b ^ (b >> 8)) & (M >> 8)).bit_count()
    return b.bit_count() + 10 * iso + 4 * rough - 2 * lines


def fits(b, typ):
    for m in TYPE_POSES[typ]:
        if not b & m:
            return True
    return False


def playable(b, tray):
    """DFS: czy da się postawić wszystkie klocki tacki (kolejność dowolna)."""
    if not tray:
        return True
    seen = set()
    for i, t in enumerate(tray):
        if t in seen:
            continue
        seen.add(t)
        rest = tray[:i] + tray[i + 1:]
        for idx in PIECE_TYPES[t]:
            for m, _, _ in POSES[idx]:
                if not b & m:
                    nb, _ = clear(b | m)
                    if playable(nb, rest):
                        return True
    return False


HARD_TRIPLES = []  # (trójka typów, waga multizbioru / 125)
for _a in range(5):
    for _b in range(_a, 5):
        for _c in range(_b, 5):
            _t = (HARD_TYPES[_a], HARD_TYPES[_b], HARD_TYPES[_c])
            _n = len({_a, _b, _c})
            HARD_TRIPLES.append((_t, {3: 6, 2: 3, 1: 1}[_n] / 125))


class SurvivalPolicy:
    name = "survival"

    def __init__(self, beam=150, final=24, samples=30, hard_w=60, risk_w=300, triple_w=400):
        self.triple_w = triple_w
        self.beam, self.final = beam, final
        self.samples, self.hard_w, self.risk_w = samples, hard_w, risk_w
        self.rng = random.Random(0)

    def reset(self, game_seed):
        self.rng = random.Random(f"surv:{game_seed}")

    @staticmethod
    def _board(game):
        b = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b |= 1 << (y * 8 + x)
        return b

    def _risk(self, b):
        r = 0.0
        for tray, w in HARD_TRIPLES:
            if not playable(b, tray):
                r += self.triple_w * w
        for t in HARD_TYPES:
            if not fits(b, t):
                r += self.hard_w
        if b.bit_count() >= 16:
            bad = 0
            for _ in range(self.samples):
                tray = tuple(self.rng.randrange(15) for _ in range(3))
                if not playable(b, tray):
                    bad += 1
            r += self.risk_w * bad / self.samples
        return r

    def act(self, game, actions):
        pieces = tuple((i, p.index) for i, p in enumerate(game.pieces) if p is not None)
        states = [(0.0, self._board(game), pieces, None)]
        leaves = []
        while states:
            nxt = []
            for _, b, rem, first in states:
                moved = False
                for k, (i, pi) in enumerate(rem):
                    r2 = rem[:k] + rem[k + 1:]
                    for m, x, y in POSES[pi]:
                        if b & m:
                            continue
                        moved = True
                        nb, n = clear(b | m)
                        f = first if first is not None else (i, x, y)
                        if r2:
                            nxt.append((cheap(nb, n), nb, r2, f))
                        else:
                            leaves.append((cheap(nb, n), nb, f))
                if not moved and first is not None:
                    leaves.append((cheap(b, 0) + 1000, b, first))
            nxt.sort(key=lambda s: s[0])
            seen, states = set(), []
            for s in nxt:
                key = (s[1], s[2])
                if key not in seen:
                    seen.add(key)
                    states.append(s)
                    if len(states) >= self.beam:
                        break
        if not leaves:
            return actions[0]
        leaves.sort(key=lambda s: s[0])
        best, best_first = None, leaves[0][2]
        for sc, b, f in leaves[: self.final]:
            v = sc + (self._risk(b) if sc < 1000 else 0)
            if best is None or v < best:
                best, best_first = v, f
        return best_first
