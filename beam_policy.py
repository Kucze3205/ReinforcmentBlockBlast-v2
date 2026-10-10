"""Polityka przeżycia: wiązka po tacce na bitboardach (bit = y*8 + x)."""
import random

from pieces import PIECE_POOL, PIECE_TYPES

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_NOT_COL0 = _FULL & ~_COLS[0]
_NOT_COL7 = _FULL & ~_COLS[7]
_LOW56 = (1 << 56) - 1
W = {"trans": 3.0, "isolated": 4.0, "filled": 0.5, "fit": 1.5, "dead": 0.0}
BEAM = 100
FIT_LEAVES = 30

_POSE_MASKS = []  # dla pozy: lista (x, y, maska)
for _p in PIECE_POOL:
    _h, _w = len(_p.shape), len(_p.shape[0])
    _lst = []
    for _y in range(8 - _h + 1):
        for _x in range(8 - _w + 1):
            _m = 0
            for _dy, _row in enumerate(_p.shape):
                for _dx, _c in enumerate(_row):
                    if _c:
                        _m |= 1 << ((_y + _dy) * 8 + _x + _dx)
            _lst.append((_x, _y, _m))
    _POSE_MASKS.append(_lst)
_ID = {id(p): p.index for p in PIECE_POOL}


def _clear(b):
    full = 0
    for m in _ROWS:
        if b & m == m:
            full |= m
    for m in _COLS:
        if b & m == m:
            full |= m
    return b & ~full


def _cheap(b):
    t = bin((b ^ (b >> 1)) & _NOT_COL7).count("1")
    t += bin((b ^ (b >> 8)) & _LOW56).count("1")
    e = ~b & _FULL
    # pusta komórka, której wszyscy sąsiedzi są zajęci lub poza planszą
    nb = (((b << 1) & _NOT_COL0) | _COLS[0]) & (((b >> 1) & _NOT_COL7) | _COLS[7]) \
        & (((b << 8) & _FULL) | _ROWS[0]) & ((b >> 8) | _ROWS[7])
    iso = bin(e & nb).count("1")
    v = W["trans"] * t + W["isolated"] * iso + W["filled"] * bin(b).count("1")
    if W["dead"]:
        v += W["dead"] * _dead_types(b)
    return v


_DEAD = {}


def _dead_types(b):
    """Ile z 15 typów klocków nie ma żadnego położenia na planszy b."""
    r = _DEAD.get(b)
    if r is None:
        r = sum(1 for poses in PIECE_TYPES
                if not any(not b & m for i in poses for _, _, m in _POSE_MASKS[i]))
        if len(_DEAD) > 300000:
            _DEAD.clear()
        _DEAD[b] = r
    return r


def _fit(b):
    n = 0
    for lst in _POSE_MASKS:
        for _, _, m in lst:
            if not b & m:
                n += 1
                break
    return n


def _tray_ok(b, poses):
    """Czy da się postawić wszystkie klocki tacki w jakiejś kolejności."""
    if not poses:
        return True
    for k, pose in enumerate(poses):
        left = poses[:k] + poses[k + 1:]
        for _, _, m in _POSE_MASKS[pose]:
            if not b & m and _tray_ok(_clear(b | m), left):
                return True
    return False


_TYPES = [[p.index for p in PIECE_POOL if p.type_index == t] for t in range(15)]
RISK_TRAYS = 12
RISK_W = 25.0


def _trays(rng):
    out = []
    for _ in range(RISK_TRAYS):
        out.append(tuple(rng.choice(rng.choice(_TYPES)) for _ in range(3)))
    return out


class BeamPolicy:
    name = "beam"

    def reset(self, game_seed):
        self._rng = random.Random(f"risk:{game_seed}")

    def act(self, game, actions):
        board = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    board |= 1 << (y * 8 + x)
        rest = tuple((i, _ID[id(p)]) for i, p in enumerate(game.pieces) if p is not None)
        beam = [(0.0, board, None, rest)]
        done = []
        while beam:
            nxt = {}
            for _, b, first, rem in beam:
                if not rem:
                    done.append((b, first))
                    continue
                for k, (idx, pose) in enumerate(rem):
                    left = rem[:k] + rem[k + 1:]
                    for x, y, m in _POSE_MASKS[pose]:
                        if b & m:
                            continue
                        nb = _clear(b | m)
                        key = (nb, left)
                        if key not in nxt:
                            nxt[key] = (_cheap(nb), nb, first or (idx, x, y), left)
            beam = sorted(nxt.values(), key=lambda s: s[0])[:BEAM]
        if not done:
            return actions[0]
        done.sort(key=lambda s: _cheap(s[0]))
        trays = _trays(self._rng)
        best, bs = None, None
        for b, first in done[:FIT_LEAVES]:
            bad = sum(not _tray_ok(b, t) for t in trays)
            s = _cheap(b) - W["fit"] * _fit(b) + RISK_W * bad
            if bs is None or s < bs:
                best, bs = first, s
        return best if best in actions else actions[0]


def build(weights=None):
    return BeamPolicy()
