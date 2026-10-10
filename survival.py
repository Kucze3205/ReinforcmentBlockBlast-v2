"""
Polityka przeżycia: wiązka po tacce na bitboardach + ryzyko niegrywalnej następnej tacki.

Plansza to 64-bitowa liczba (bit = y*8 + x). Z bieżącej tacki budujemy wiązką kolejności
i położenia klocków (tanie cechy), a kilka najlepszych liści ocenia drogo: kara za trudne
tacki następne (dokładne trójki 5 trudnych typów ważone multizbiorem), za losowe tacki
oraz liczba póz mieszczących się na planszy.
"""
import itertools
import random

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
ROWS = [0xFF << (8 * y) for y in range(8)]
COLS = [sum(1 << (8 * y + x) for y in range(8)) for x in range(8)]
NOT_A = FULL & ~COLS[0]
NOT_H = FULL & ~COLS[7]

# PLACE[poza] = [(maska, x, y)]
PLACE = []
for _p in PIECE_POOL:
    _h, _w = len(_p.shape), len(_p.shape[0])
    _lst = []
    for _y in range(8 - _h + 1):
        for _x in range(8 - _w + 1):
            _m = 0
            for _dy, _row in enumerate(_p.shape):
                for _dx, _c in enumerate(_row):
                    if _c:
                        _m |= 1 << (8 * (_y + _dy) + _x + _dx)
            _lst.append((_m, _x, _y))
    PLACE.append(_lst)

HARD_TYPES = [3, 4, 7, 6, 10]  # belka4, belka5, kwadrat3, prostokąt 2x3, narożnik5
HARD_TRIPLES = [
    (c, len(set(itertools.permutations(c))) / 125.0)
    for c in itertools.combinations_with_replacement(range(len(HARD_TYPES)), 3)
]

BEAM = 40
FINAL = 8
FINAL_TIGHT = 20
HARD_W = 400.0
RAND_W = 150.0
RAND_N = 10
MOB_W = 1.0
LINE_W = 0.0
LA_W = 0.0
LA_BEAM = 6
LA_DEAD = -300.0
FILL_W = 1.0
ISO_W = 10.0
TRANS_W = 5.0


def _pop(v):
    return bin(v).count("1")


if hasattr(int, "bit_count"):
    def _pop(v):  # noqa: F811
        return v.bit_count()


def clear(b):
    full = 0
    for r in ROWS:
        if b & r == r:
            full |= r
    for c in COLS:
        if b & c == c:
            full |= c
    return b & ~full if full else b


def cheap(b):
    e = ~b & FULL
    nb = ((e << 1) & NOT_A) | ((e >> 1) & NOT_H) | (e << 8) | (e >> 8)
    iso = _pop(e & ~(nb & FULL))
    trans = _pop((b ^ (b >> 1)) & NOT_H) + _pop(b ^ (b >> 8))
    line = 0
    for r in ROWS:
        n = _pop(b & r)
        line += n * n
    for c in COLS:
        n = _pop(b & c)
        line += n * n
    return -_pop(b) * FILL_W - iso * ISO_W - trans * TRANS_W + line * LINE_W


def fits(b, pose):
    for m, _, _ in PLACE[pose]:
        if not b & m:
            return True
    return False


def tray_ok(b, poses):
    """Czy da się postawić wszystkie klocki tacki (w dowolnej kolejności)."""
    if not poses:
        return True
    seen = set()
    for i, p in enumerate(poses):
        if p in seen:
            continue
        seen.add(p)
        rest = poses[:i] + poses[i + 1:]
        for m, _, _ in PLACE[p]:
            if not b & m and tray_ok(clear(b | m), rest):
                return True
    return False


def board_bits(grid):
    b = 0
    for y in range(8):
        row = grid[y]
        for x in range(8):
            if row[x]:
                b |= 1 << (8 * y + x)
    return b


class SurvivalPolicy:
    name = "survival"

    def __init__(self):
        self.reset(0)

    def reset(self, game_seed):
        self.rng = random.Random(f"surv:{game_seed}")
        self.plan = []
        self.exp = []
        self.expect = None

    def act(self, game, actions):
        b = board_bits(game.board.grid)
        if self.plan and self.expect == b and self.plan[0] in actions:
            a = self.plan[0]
            self.plan = self.plan[1:]
            self.expect = self.exp[0] if self.exp else None
            self.exp = self.exp[1:]
            return a
        self.plan = []
        tray = [(i, p.index) for i, p in enumerate(game.pieces) if p is not None]
        seq, boards = self._search(b, tray)
        if not seq or seq[0] not in actions:
            return actions[0]
        self.plan = list(seq[1:])
        self.exp = list(boards[1:])
        self.expect = boards[0]
        return seq[0]

    def _search(self, b, tray):
        n = len(tray)
        states = [(b, 0, (), ())]
        for _ in range(n):
            nxt = {}
            for brd, used, seq, bs in states:
                for k, (idx, pose) in enumerate(tray):
                    if used >> k & 1:
                        continue
                    for m, x, y in PLACE[pose]:
                        if brd & m:
                            continue
                        nb = clear(brd | m)
                        key = (nb, used | 1 << k)
                        if key not in nxt:
                            nxt[key] = (nb, used | 1 << k, seq + ((idx, x, y),), bs + (nb,))
            if not nxt:
                break
            states = sorted(nxt.values(), key=lambda s: -cheap(s[0]))[:BEAM]
        if not states[0][2]:
            return None, None
        uniq = {}
        for s in states:
            uniq.setdefault((s[0], len(s[2])), s)
        cand = sorted(uniq.values(), key=lambda s: -cheap(s[0]))
        final = FINAL_TIGHT if 64 - _pop(b) <= 22 else FINAL
        cand = cand[:final]
        hard = [self.rng.choice(PIECE_TYPES[t]) for t in HARD_TYPES]
        rand = [[self.rng.choice(PIECE_TYPES[self.rng.randrange(15)]) for _ in range(3)]
                for _ in range(RAND_N)]
        best, best_s = None, None
        for s in cand:
            sc = self._deep(s[0], hard, rand) - 1e5 * (n - len(s[2]))
            if best_s is None or sc > best_s:
                best, best_s = s, sc
        return list(best[2]), list(best[3])

    def _lookahead(self, b, poses):
        """Najlepsza tania ocena planszy po postawieniu całej tacki; LA_DEAD gdy się nie da."""
        states = {(b, 0): b}
        for _ in poses:
            nxt = {}
            for (brd, used), _b in states.items():
                for k, pose in enumerate(poses):
                    if used >> k & 1:
                        continue
                    for m, _, _ in PLACE[pose]:
                        if not brd & m:
                            nb = clear(brd | m)
                            nxt[(nb, used | 1 << k)] = nb
            if not nxt:
                return LA_DEAD
            states = dict(sorted(nxt.items(), key=lambda kv: -cheap(kv[1]))[:LA_BEAM])
        return max(cheap(v) for v in states.values())

    def _deep(self, b, hard, rand):
        sc = cheap(b)
        if LA_W:
            sc += LA_W * sum(self._lookahead(b, t) for t in rand) / len(rand)
        bad = 0.0
        for c, w in HARD_TRIPLES:
            if not tray_ok(b, [hard[i] for i in c]):
                bad += w
        sc -= HARD_W * bad
        r = sum(1 for t in rand if not tray_ok(b, t))
        sc -= RAND_W * r / len(rand)
        mob = sum(1 for p in range(len(PLACE)) if fits(b, p))
        return sc + MOB_W * mob
