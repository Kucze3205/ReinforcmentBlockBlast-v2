"""
Polityka przeżycia: przeszukanie wiązką całej tacki (wszystkie kolejności) na
bitboardach + ocena planszy + ryzyko następnej, losowej tacki.

Cel to nieprzegrywanie (CONTEXT.md), więc punkty nie wchodzą do oceny poza
drobną premią za czyszczenie linii, która utrzymuje planszę pustą.
"""
import random
from functools import lru_cache
from itertools import permutations

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
ROWS = [0xFF << (8 * r) for r in range(8)]
COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
LINES = ROWS + COLS
EDGE_L = COLS[0]
EDGE_R = COLS[7]

PLACE = []  # PLACE[poza] = maski bitowe wszystkich położeń
for _p in PIECE_POOL:
    _h, _w = len(_p.shape), len(_p.shape[0])
    PLACE.append([
        (sum(1 << (8 * (y + dy) + x + dx)
             for dy, row in enumerate(_p.shape) for dx, c in enumerate(row) if c), x, y)
        for y in range(8 - _h + 1) for x in range(8 - _w + 1)
    ])
NPOSE = len(PLACE)

W = {"trans": 3.0, "isolated": 2.0, "fit": 1.5, "fill": 0.5, "risk": 300.0, "dead": 300.0, "own": 0.5, "clear": 5.0, "sq": 0.0, "near": 0.0, "bonus": 400.0}
BEAM = 24
FITCAP = 3
TOP = 4
SAMPLES = 6
LBEAM = 6


def pop(x):
    return x.bit_count()


def clear(b):
    full = 0
    n = 0
    for m in LINES:
        if b & m == m:
            full |= m
            n += 1
    return b & ~full, n


ERODE = []  # (przesunięcia komórek, maska poprawnych kotwic) dla każdej pozy
for _p, _ms in zip(PIECE_POOL, PLACE):
    _cells = [8 * dy + dx for dy, row in enumerate(_p.shape) for dx, c in enumerate(row) if c]
    _anch = sum(1 << (8 * y + x) for _, x, y in _ms)
    ERODE.append((_cells, _anch))


def fits(b):
    """Ile póz (z 41) ma jakiekolwiek miejsce na planszy."""
    e = ~b & FULL
    n = 0
    for cells, anch in ERODE:
        r = anch
        for c in cells:
            r &= e >> c
            if not r:
                break
        if r:
            n += min(pop(r), FITCAP)
    return n


NOT_LAST_COL = 0x7F7F7F7F7F7F7F7F


def cheap(b):
    # przejścia pusty/pełny w wierszach i kolumnach, ściana liczy się jako pełna
    trans = pop(((b ^ (b >> 1)) & NOT_LAST_COL)) + pop(b & EDGE_L) + pop(b & EDGE_R) \
        + pop((b ^ (b >> 8)) & (FULL >> 8)) + pop(b & ROWS[0]) + pop(b & ROWS[7])
    around = (((b << 1) & FULL) | EDGE_L) & ((b >> 1) | EDGE_R) \
        & (((b << 8) & FULL) | ROWS[0]) & ((b >> 8) | ROWS[7])
    iso = pop(~b & around & FULL)
    sq = near = 0
    for m in LINES:
        c = pop(b & m)
        sq += c * c
        near += c >= 6
    return -(W["trans"] * trans + W["isolated"] * iso + W["fill"] * pop(b)) \
        + W["sq"] * sq + W["near"] * near


@lru_cache(maxsize=1 << 20)
def evaluate(b):
    return cheap(b) + W["fit"] * fits(b)


def playable(b, poses):
    """Czy da się ułożyć wszystkie klocki w jakiejś kolejności (DFS, bez oceny)."""
    if not poses:
        return True
    for i, k in enumerate(poses):
        if i and poses[i] in poses[:i]:
            continue
        rest = poses[:i] + poses[i + 1:]
        for m, _, _ in PLACE[k]:
            if not b & m and playable(clear(b | m)[0], rest):
                return True
    return False


def search(b, poses, beam=BEAM):
    """Najlepszy liść dla każdej pierwszej akcji: lista (wartość, (poza, maska), plansza)."""
    res = {}
    for order in set(permutations(poses)):
        states = [(b, 0.0, None)]
        for k in order:
            nxt = {}
            for sb, bonus, first in states:
                for m, px, py in PLACE[k]:
                    if sb & m:
                        continue
                    nb, cl = clear(sb | m)
                    f = first if first is not None else (k, px, py)
                    gain = bonus + W["clear"] * cl + (W["bonus"] if nb == 0 else 0.0)
                    key = (nb, f)
                    if key not in nxt or nxt[key][1] < gain:
                        nxt[key] = (nb, gain, f)
            if not nxt:
                states = []
                break
            states = list(nxt.values())
            if len(states) > beam:
                states.sort(key=lambda s: evaluate(s[0]) + s[1], reverse=True)
                states = states[:beam]
        for sb, bonus, first in states:
            v = evaluate(sb) + bonus
            if first not in res or res[first][0] < v:
                res[first] = (v, first, sb)
    return list(res.values())


class SurvivalPolicy:
    name = "survival"

    def reset(self, game_seed):
        self.rng = random.Random(f"surv:{game_seed}")

    def tray(self):
        return [self.rng.choice(PIECE_TYPES[self.rng.randrange(len(PIECE_TYPES))]) for _ in range(3)]

    def look(self, b):
        """Średnia ocena najlepszego ułożenia próbnych następnych tacek; martwa tacka = -DEAD."""
        tot = 0.0
        for _ in range(SAMPLES):
            res = search(b, self.tray(), beam=LBEAM)
            tot += max(r[0] for r in res) if res else -W["dead"]
        return tot / SAMPLES

    def act(self, game, actions):
        b = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b |= 1 << (8 * y + x)
        slot = {}
        for i, p in enumerate(game.pieces):
            if p is not None:
                slot.setdefault(p.index, i)
        leaves = search(b, [p.index for p in game.pieces if p is not None])
        if not leaves:
            return actions[0]
        leaves.sort(key=lambda t: t[0], reverse=True)
        leaves = leaves[:TOP]
        if len(leaves) > 1:
            leaves = [(W["own"] * v + self.look(sb), f, sb) for v, f, sb in leaves]
            leaves.sort(key=lambda t: t[0], reverse=True)
        k, px, py = leaves[0][1]
        return (slot[k], px, py)
