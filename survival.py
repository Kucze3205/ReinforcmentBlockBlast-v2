"""
Polityka przeżycia: wiązka po tacce na bitboardach (bit = 8*y + x).

Cel to nieprzegrywanie (CONTEXT.md), więc punkty są ignorowane. Plan na całą
tackę liczony raz (permutacje kolejności, wiązka po ruchach), potem wykonywany.
"""
import random
from itertools import permutations

from pieces import PIECE_POOL, PIECE_TYPES

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_NOT_COL0 = _FULL & ~_COLS[0]
_NOT_COL7 = _FULL & ~_COLS[7]
_LINES = _ROWS + _COLS


def _pose_masks(piece):
    h, w = len(piece.shape), len(piece.shape[0])
    base = 0
    for dy, row in enumerate(piece.shape):
        for dx, c in enumerate(row):
            if c:
                base |= 1 << (8 * dy + dx)
    return [(base << (8 * y + x), x, y) for y in range(9 - h) for x in range(9 - w)]


_POSE = {p.index: _pose_masks(p) for p in PIECE_POOL}
_TYPE_POSES = [[[m for m, _, _ in _POSE[i]] for i in idxs] for idxs in PIECE_TYPES]

W_ISO, W_TRANS, W_FILL, W_LINE, W_ZERO, W_FIT = 30, 4, 1.0, 6, 400, 3
W_RISK = 200


def _clear(b):
    full = 0
    for m in _LINES:
        if b & m == m:
            full |= m
    return b & ~full, full != 0


def _cheap(b):
    empty = ~b & _FULL
    left = ((b << 1) & _NOT_COL0) | _COLS[0]
    right = ((b >> 1) & _NOT_COL7) | _COLS[7]
    up = ((b << 8) & _FULL) | _ROWS[0]
    down = (b >> 8) | _ROWS[7]
    iso = (empty & left & right & up & down).bit_count()
    trans = ((b ^ (b >> 1)) & _NOT_COL7).bit_count() + ((b ^ (b >> 8)) & ~_ROWS[7] & _FULL).bit_count()
    return -(W_ISO * iso + W_TRANS * trans + W_FILL * b.bit_count())


def _fit(b):
    """Luz na typy klocków; typ bez żadnego położenia dostaje wysoką karę."""
    s = 0
    for poses in _TYPE_POSES:
        n = 0
        for masks in poses:
            for m in masks:
                if not b & m:
                    n += 1
                    if n >= 4:
                        break
            if n >= 4:
                break
        s += W_FIT * n if n else -W_ZERO
    return s / 15.0


def _playable(b, poses_list):
    """Czy tacka (lista list masek-ułożeń) da się w całości postawić w jakiejkolwiek kolejności."""
    if not poses_list:
        return True
    for k, poses in enumerate(poses_list):
        rest = poses_list[:k] + poses_list[k + 1:]
        for m in poses:
            if not b & m:
                nb, _ = _clear(b | m)
                if _playable(nb, rest):
                    return True
    return False


class SurvivalPolicy:
    name = "survival"
    BEAM = 8
    FINAL = 10
    SAMPLES = 40

    def reset(self, game_seed):
        self.plan = []
        self.rng = random.Random(1234)

    def _risk(self, b):
        bad = 0
        for t in self.trays:
            if not _playable(b, t):
                bad += 1
        return bad

    def act(self, game, actions):
        if self.plan:
            a = self.plan.pop(0)
            if a in actions:
                return a
        self.plan = self._search(game)
        if self.plan:
            a = self.plan.pop(0)
            if a in actions:
                return a
        self.plan = []
        return actions[0]

    def _search(self, game):
        b0 = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b0 |= 1 << (8 * y + x)
        idxs = [i for i, p in enumerate(game.pieces) if p is not None]
        leaves = []
        seen = set()
        for order in permutations(idxs):
            states = [(b0, ())]
            complete = True
            for k, i in enumerate(order):
                nxt = {}
                for b, path in states:
                    for m, x, y in _POSE[game.pieces[i].index]:
                        if b & m:
                            continue
                        nb, cl = _clear(b | m)
                        if nb not in nxt:
                            nxt[nb] = (nb, path + ((i, x, y),), cl)
                cand = list(nxt.values())
                if not cand:
                    complete = False
                    break
                if k < len(order) - 1:
                    cand.sort(key=lambda t: _cheap(t[0]) + (W_LINE if t[2] else 0), reverse=True)
                    cand = cand[: self.BEAM]
                states = [(nb, p) for nb, p, _ in cand]
            pen = 0 if complete else 5000
            for nb, p in states:
                if (nb, len(p)) not in seen:
                    seen.add((nb, len(p)))
                    leaves.append((_cheap(nb) - pen, nb, p, complete))
        if not leaves:
            return []
        leaves.sort(key=lambda t: t[0], reverse=True)
        self.trays = []
        for _ in range(self.SAMPLES):
            tray = []
            for _ in range(3):
                ti = self.rng.randrange(15)
                pi = self.rng.choice(PIECE_TYPES[ti])
                tray.append([m for m, _, _ in _POSE[pi]])
            self.trays.append(tray)
        best, best_s = None, None
        for c, nb, p, ok in leaves[: self.FINAL]:
            s = c + (-W_RISK * self._risk(nb) if ok else -1e6)
            if best_s is None or s > best_s:
                best, best_s = p, s
        return list(best)
