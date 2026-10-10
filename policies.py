"""
Polityki grające, których używa benchmark.

Wszystkie są deterministyczne przy zadanym seedzie partii — benchmark mierzy,
co polityka umie, a nie jak wypada w trakcie nauki (#8).
"""
import random

from board import Board
from scoring import FULL_CLEAR_BONUS, clear_points, placement_points


class RandomPolicy:
    """Jednostajnie po dostępnych ruchach. Dolna granica odniesienia."""

    name = "random"

    def __init__(self, seed=0):
        self._seed = seed

    def reset(self, game_seed):
        self.rng = random.Random(f"{self._seed}:{game_seed}")

    def act(self, game, actions):
        return self.rng.choice(actions)


class GreedyPolicy:
    """Maksymalizuje punkty z bieżącego postawienia (jeden pół-ruch w przód)."""

    name = "greedy"

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        best, best_gain = actions[0], None
        for action in actions:
            gain = _immediate_gain(game, action)
            if best_gain is None or gain > best_gain:
                best, best_gain = action, gain
        return best


class ModelPolicy:
    """Wytrenowana sieć w trybie deterministycznym (ε = 0)."""

    def __init__(self, agent, name):
        self.agent = agent
        self.name = name

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        grid, shapes, numeric, _ = self.agent.get_state(game)
        move = self.agent.get_action((grid, shapes, numeric), epsilon=0.0)
        return tuple(move)


def _immediate_gain(game, action):
    """Punkty, które da to postawienie — wg skalibrowanego wzoru, bez zmiany stanu gry."""
    idx, x, y = action
    piece = game.pieces[idx]
    board = game.board.copy()
    board.place_piece(piece, x, y)

    gain = placement_points(piece)
    rows, cols = board.check_full_lines()
    lines = len(rows) + len(cols)
    if lines > 0:
        gain += clear_points(game.combo + 1, lines)
        board.clear_lines(rows, cols)
        if not any(any(row) for row in board.grid):
            gain += FULL_CLEAR_BONUS
    return gain


# --- Polityka przeżycia: wiązka po tacce na bitboardach + ryzyko próbnych następnych tacek ---

import itertools

from pieces import PIECE_POOL, PIECE_TYPES

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * i) for i in range(8)]
_COLS = [sum(1 << (8 * y + x) for y in range(8)) for x in range(8)]
_COL0, _COL7, _ROW0, _ROW7 = _COLS[0], _COLS[7], _ROWS[0], _ROWS[7]


def _pose_masks(piece):
    h, w = len(piece.shape), len(piece.shape[0])
    base = 0
    for dy, row in enumerate(piece.shape):
        for dx, cell in enumerate(row):
            if cell:
                base |= 1 << (8 * dy + dx)
    return [(base << (8 * y + x), x, y) for y in range(9 - h) for x in range(9 - w)]


_MASKS = [_pose_masks(p) for p in PIECE_POOL]
_CELLS = [sum(sum(r) for r in p.shape) for p in PIECE_POOL]
# Trudne typy: 3x3, duże L, belka 5, prostokąt 2x3, przekątna 3
_HARD_TYPES = [7, 10, 4, 6, 12]


def _settle(b):
    """Czyści pełne linie; zwraca (plansza, liczba linii)."""
    clr = 0
    n = 0
    for m in _ROWS:
        if b & m == m:
            clr |= m
            n += 1
    for m in _COLS:
        if b & m == m:
            clr |= m
            n += 1
    return b & ~clr, n


def _playable(b, poses):
    """Czy da się postawić wszystkie klocki tacki w pewnej kolejności."""
    if not poses:
        return True
    for i, p in enumerate(poses):
        rest = poses[:i] + poses[i + 1:]
        for m, _, _ in _MASKS[p]:
            if not b & m:
                nb, _n = _settle(b | m)
                if _playable(nb, rest):
                    return True
    return False


def _dead(b):
    """Puste komórki o >=3 zajętych sąsiadach (poza planszą = zajęte)."""
    a = ((b << 1) & _FULL & ~_COL0) | _COL0
    c = ((b >> 1) & ~_COL7) | _COL7
    d = ((b << 8) & _FULL) | _ROW0
    e = (b >> 8) | _ROW7
    three = (a & c & d) | (a & c & e) | (a & d & e) | (c & d & e)
    four = a & c & d & e
    free = ~b & _FULL
    return (three & free).bit_count() + 2 * (four & free).bit_count()


def _cheap(b):
    trans = ((b ^ (b >> 1)) & ~_COL7).bit_count() + ((b ^ (b >> 8)) & ~_ROW7).bit_count()
    return -3.0 * b.bit_count() - 14.0 * _dead(b) - 4.0 * trans


class SurvivalPolicy:
    name = "survival"

    def __init__(self, beam=20, top=12, trays=30, risk_w=500.0, hard_w=400.0):
        self.beam, self.top, self.trays = beam, top, trays
        self.risk_w, self.hard_w = risk_w, hard_w

    def reset(self, game_seed):
        self.rng = random.Random(f"surv:{game_seed}")

    def _sample_tray(self):
        r = self.rng
        return [r.choice(PIECE_TYPES[r.randrange(15)]) for _ in range(3)]

    def _risk(self, b, trays, hard):
        bad = sum(1 for t in trays if not _playable(b, t))
        hbad = sum(1 for t in hard if not _playable(b, t))
        return self.risk_w * bad / len(trays) + self.hard_w * hbad / len(hard)

    def act(self, game, actions):
        if len(actions) == 1:
            return actions[0]
        pieces = [(i, p.index) for i, p in enumerate(game.pieces) if p is not None]
        b0 = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b0 |= 1 << (8 * y + x)
        leaves = {}  # (plansza, pierwsza akcja) -> wartość
        seen_perms = set()
        for perm in itertools.permutations(pieces):
            key = tuple(p for _, p in perm)
            if key in seen_perms and len(set(key)) < len(key):
                continue
            seen_perms.add(key)
            states = {(b0, None): 0.0}
            placed = 0
            for idx, pose in perm:
                nxt = {}
                for (b, first), val in states.items():
                    for m, x, y in _MASKS[pose]:
                        if b & m:
                            continue
                        nb, n = _settle(b | m)
                        v = val + 4.0 * n + 0.1 * _CELLS[pose]
                        if nb == 0:
                            v += 60.0
                        k = (nb, first if first is not None else (idx, x, y))
                        if k not in nxt or nxt[k] < v:
                            nxt[k] = v
                if not nxt:
                    break
                placed += 1
                if len(nxt) > self.beam:
                    items = sorted(nxt.items(), key=lambda kv: kv[1] + _cheap(kv[0][0]), reverse=True)
                    nxt = dict(items[: self.beam])
                states = nxt
            for k, v in states.items():
                score = v + _cheap(k[0]) - (1e6 if placed < len(perm) else 0)
                if k not in leaves or leaves[k] < score:
                    leaves[k] = score
        ranked = sorted(leaves.items(), key=lambda kv: kv[1], reverse=True)[: self.top]
        trays = [self._sample_tray() for _ in range(self.trays)]
        hard = [
            [self.rng.choice(PIECE_TYPES[self.rng.choice(_HARD_TYPES)]) for _ in range(3)]
            for _ in range(6)
        ]
        best, best_v = None, None
        for (b, first), s in ranked:
            v = s
            if s > -5e5:
                v -= self._risk(b, trays, hard)
            if best_v is None or v > best_v:
                best, best_v = first, v
        return tuple(best) if best is not None else actions[0]


def build(weights=None):
    return SurvivalPolicy()
