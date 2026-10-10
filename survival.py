"""
Polityka przeżycia: wiązka po tacce na bitboardach (bit = y*8 + x).

Przeszukuje kolejności i położenia klocków z tacki, ocenia planszę (puste pola,
izolowane dziury, przejścia) i spośród najlepszych liści wybiera ten z najlepszym
dopasowaniem póz oraz najmniejszym ryzykiem, że następna tacka nie da się rozegrać.
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

_FULL = (1 << 64) - 1
_COL0 = 0x0101010101010101
_COL7 = _COL0 << 7
_ROW0 = 0xFF
_LOW56 = (1 << 56) - 1

BEAM = 100
FINAL = 8          # tyle liści dostaje drogą ocenę (fit + ryzyko następnej tacki)
SAMPLES = 24      # próbne tacki do oceny ryzyka
W = {"empty": 1.0, "iso": 4.0, "trans": 3.0, "fit": 1.5, "risk": 300.0, "lines": 2.0, "zero": 5.0}


def _pose_masks():
    out = []
    for p in PIECE_POOL:
        h, w = len(p.shape), len(p.shape[0])
        base = 0
        for dy, row in enumerate(p.shape):
            for dx, c in enumerate(row):
                if c:
                    base |= 1 << (dy * 8 + dx)
        out.append({(x, y): base << (y * 8 + x)
                    for y in range(8 - h + 1) for x in range(8 - w + 1)})
    return out


_MASKS = _pose_masks()
_MASK_LISTS = [list(d.values()) for d in _MASKS]


def _clear(b):
    r = b
    r &= r >> 1
    r &= r >> 2
    r &= r >> 4
    rows = r & _COL0
    c = b & (b >> 8)
    c &= c >> 16
    c &= c >> 32
    cols = c & 0xFF
    if not (rows or cols):
        return b, 0
    n = rows.bit_count() + cols.bit_count()
    return b & ~((rows * 255) | (cols * _COL0)), n


def _cheap(b):
    empty = 64 - b.bit_count()
    e = ~b & _FULL
    left = ((b << 1) & _FULL & ~_COL0) | _COL0
    right = ((b >> 1) & ~_COL7) | _COL7
    up = ((b << 8) & _FULL) | _ROW0
    down = (b >> 8) | (_ROW0 << 56)
    iso = (e & left & right & up & down).bit_count()
    trans = ((b ^ (b >> 1)) & ~_COL7).bit_count() + ((b ^ (b >> 8)) & _LOW56).bit_count()
    return W["empty"] * empty - W["iso"] * iso - W["trans"] * trans


def _fits(b, pose, cap=3):
    n = 0
    for m in _MASK_LISTS[pose]:
        if not m & b:
            n += 1
            if n >= cap:
                break
    return n


def _fit_score(b):
    tot = 0.0
    for t in PIECE_TYPES:
        n = 0
        for i in t:
            n += _fits(b, i, 4)
            if n >= 4:
                break
        tot += W["fit"] * min(n, 4) / 2.0 if n else -W["zero"]
    return tot


def _playable(b, poses):
    """Czy tackę (lista póz) da się rozegrać w całości z planszy b (DFS, z czyszczeniem)."""
    seen = set()
    stack = [(b, tuple(poses))]
    while stack:
        bb, rem = stack.pop()
        if not rem:
            return True
        if (bb, rem) in seen:
            continue
        seen.add((bb, rem))
        for k, pose in enumerate(rem):
            nxt = rem[:k] + rem[k + 1:]
            for m in _MASK_LISTS[pose]:
                if not m & bb:
                    nb, _ = _clear(bb | m)
                    stack.append((nb, nxt))
    return False


class SurvivalPolicy:
    name = "survival"

    def reset(self, game_seed):
        self.rng = random.Random(f"surv:{game_seed}")
        self.samples = [[self._rand_pose() for _ in range(3)] for _ in range(SAMPLES)]

    def _rand_pose(self):
        return self.rng.choice(self.rng.choice(PIECE_TYPES))

    def act(self, game, actions):
        if len(actions) == 1:
            return actions[0]
        b0 = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b0 |= 1 << (y * 8 + x)
        tray = [p.index if p else -1 for p in game.pieces]
        slots = tuple(i for i, p in enumerate(tray) if p >= 0)
        level = {(b0, slots): (0.0, None, 0)}
        dead = []
        for _ in range(len(slots)):
            nxt = {}
            for (b, rem), (_, first, lines) in level.items():
                moved = False
                for s in rem:
                    r2 = tuple(k for k in rem if k != s)
                    for (x, y), m in _MASKS[tray[s]].items():
                        if m & b:
                            continue
                        moved = True
                        nb, n = _clear(b | m)
                        key = (nb, r2)
                        if key not in nxt:
                            f = first if first is not None else (s, x, y)
                            nxt[key] = (_cheap(nb) + W["lines"] * (lines + n), f, lines + n)
                if not moved:
                    dead.append((_cheap(b) - 1e6, b, first))
            if len(nxt) > BEAM:
                nxt = dict(sorted(nxt.items(), key=lambda kv: -kv[1][0])[:BEAM])
            level = nxt
        cand = [(sc, b, first) for (b, _), (sc, first, _) in level.items()]
        cand.sort(key=lambda t: -t[0])
        best, best_v = None, None
        for sc, b, first in cand[:FINAL]:
            v = sc + _fit_score(b)
            bad = sum(1 for s in self.samples if not _playable(b, s))
            v -= W["risk"] * bad / len(self.samples)
            if best_v is None or v > best_v:
                best, best_v = first, v
        if best is None:
            dead.sort(key=lambda t: -t[0])
            best = next((d[2] for d in dead if d[2] is not None), None)
        return best if best is not None else actions[0]
