"""Polityka przeżycia: wiązka po tacce na bitboardach, liście oceniane cechami i ryzykiem trudnych tacek."""
import itertools
import random

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
ROWS = [0xFF << (8 * y) for y in range(8)]
COLS = [sum(1 << (8 * y + x) for y in range(8)) for x in range(8)]
NOT_A = FULL & ~COLS[0]
NOT_H = FULL & ~COLS[7]
LEFT, RIGHT, TOP, BOTTOM = COLS[0], COLS[7], ROWS[0], ROWS[7]
WALLS = LEFT | RIGHT | TOP | BOTTOM

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
HARD_TRIPLES = []
for _c in itertools.combinations_with_replacement(range(len(HARD_TYPES)), 3):
    _slots = tuple(_c[:_j].count(_c[_j]) for _j in range(3))
    HARD_TRIPLES.append((_c, _slots, len(set(itertools.permutations(_c))) / 125.0))

BEAM = 40
FINAL = 8
FINAL_TIGHT = 20
OCC_W = 1.4
POCKET_W = 0.75
EDGE_W = 1.5
WALL_W = 2.0
LINE_W = 4.2
RISK_W = 400.0
FIT_W = 80.0
DEAD_W = 12.3
HARD_W = 400.0

try:
    _pop = int.bit_count
except AttributeError:
    def _pop(v):
        return bin(v).count("1")


def clear(b):
    kill = 0
    lines = 0
    for m in ROWS:
        if b & m == m:
            kill |= m
            lines += 1
    for m in COLS:
        if b & m == m:
            kill |= m
            lines += 1
    return b & ~kill, lines


def cheap(b):
    empty = ~b & FULL
    a = ((b << 1) & NOT_A) | LEFT
    r = ((b >> 1) & NOT_H) | RIGHT
    u = (b << 8) | TOP
    d = (b >> 8) | BOTTOM
    pockets = (a & r & u) | (a & r & d) | (a & u & d) | (r & u & d)
    edges = _pop((b ^ (b >> 1)) & NOT_H) + _pop(b ^ (b >> 8))
    walls = _pop(empty & WALLS)
    return (-OCC_W * _pop(b) - POCKET_W * _pop(pockets & empty)
            - EDGE_W * edges - WALL_W * walls)


def fit_stats(b):
    tot = 0.0
    dead = 0
    for poses in PIECE_TYPES:
        fit = sum(1 for p in poses if any(not b & m for m, _, _ in PLACE[p]))
        if fit == 0:
            dead += 1
        tot += fit / len(poses)
    return tot / len(PIECE_TYPES), dead


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
            if not b & m and tray_ok(clear(b | m)[0], rest):
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
        states = [(b, 0, tuple(range(n)), (), ())]
        for _ in range(n):
            nxt = {}
            for brd, lines, rem, seq, bs in states:
                for k in rem:
                    idx, pose = tray[k]
                    rest = tuple(r for r in rem if r != k)
                    for m, x, y in PLACE[pose]:
                        if brd & m:
                            continue
                        nb, ln = clear(brd | m)
                        cum = lines + ln
                        sc = cheap(nb) + LINE_W * cum
                        key = (nb, rest)
                        cur = nxt.get(key)
                        if cur is None or sc > cur[0]:
                            nxt[key] = (sc, nb, cum, rest, seq + ((idx, x, y),), bs + (nb,))
            if not nxt:
                break
            states = [v[1:] for v in sorted(nxt.values(), key=lambda v: -v[0])[:BEAM]]
        if not states[0][3]:
            return None, None
        final = FINAL_TIGHT if 64 - _pop(b) <= 22 else FINAL
        hard = [[self.rng.choice(PIECE_TYPES[t]) for _ in range(3)] for t in HARD_TYPES]
        best, best_s = None, None
        for brd, lines, _rem, seq, bs in states[:final]:
            sc = self._leaf(brd, lines, hard)
            if best_s is None or sc > best_s:
                best, best_s = (seq, bs), sc
        return list(best[0]), list(best[1])

    def _leaf(self, b, lines, hard):
        mean_fit, dead = fit_stats(b)
        bad = 0.0
        for c, slots, w in HARD_TRIPLES:
            if not tray_ok(b, [hard[i][s] for i, s in zip(c, slots)]):
                bad += w
        return (cheap(b) + LINE_W * lines - RISK_W * (1.0 - mean_fit) ** 3
                - FIT_W * (1.0 - mean_fit) - DEAD_W * dead - HARD_W * bad)
