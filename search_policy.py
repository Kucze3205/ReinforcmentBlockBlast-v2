"""
Polityka przeżycia: przeszukanie całej tacki (kolejność x miejsca) na bitboardzie
z heurystyką izolowanych dziur / przejść / ruchliwości. Bez wag, deterministyczna.
"""
from pieces import PIECE_POOL

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_LINES = _ROWS + _COLS

_MASKS = {}


def _masks(piece):
    m = _MASKS.get(piece.index)
    if m is None:
        h, w = len(piece.shape), len(piece.shape[0])
        base = 0
        for dy, row in enumerate(piece.shape):
            for dx, cell in enumerate(row):
                if cell:
                    base |= 1 << (8 * dy + dx)
        m = _MASKS[piece.index] = [
            (x, y, base << (8 * y + x)) for y in range(8 - h + 1) for x in range(8 - w + 1)
        ]
    return m


_PROBE = []


def _probe():
    if not _PROBE:
        _PROBE.extend([m for _, _, m in _masks(p)] for p in PIECE_POOL)
    return _PROBE


def _clear(b):
    full = 0
    n = 0
    for l in _LINES:
        if b & l == l:
            full |= l
            n += 1
    return b & ~full, n


def _evaluate(b):
    left = (((b << 1) & _FULL) & ~_COLS[0]) | _COLS[0]
    right = ((b >> 1) & ~_COLS[7]) | _COLS[7]
    up = ((b << 8) & _FULL) | _ROWS[0]
    down = (b >> 8) | _ROWS[7]
    free = ~b & _FULL
    c3 = (left & right & up) | (left & right & down) | (left & up & down) | (right & up & down)
    c4 = left & right & up & down
    n3 = bin(free & c3).count("1")
    n4 = bin(free & c4).count("1")
    trans = bin((b ^ (b >> 1)) & ~_COLS[7]).count("1") + bin((b ^ (b >> 8)) & ~_ROWS[7]).count("1")
    mob = 0
    for ms in _probe():
        for m in ms:
            if not b & m:
                mob += 1
                break
    return 6.0 * mob - 8.0 * n3 - 12.0 * n4 - 1.5 * trans - 1.0 * bin(b).count("1")


class SearchPolicy:
    name = "search"
    BEAM = 10

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        board = 0
        for y, row in enumerate(game.board.grid):
            for x, v in enumerate(row):
                if v:
                    board |= 1 << (8 * y + x)
        idxs = [i for i, p in enumerate(game.pieces) if p is not None]
        state = {"val": -1e18, "first": None}

        def rec(b, rest, first, bonus):
            if not rest:
                v = _evaluate(b) + bonus
                if v > state["val"]:
                    state["val"], state["first"] = v, first
                return
            cands = []
            for i in rest:
                for x, y, m in _masks(game.pieces[i]):
                    if b & m:
                        continue
                    nb, n = _clear(b | m)
                    cands.append((_evaluate(nb) + 40.0 * n * n, i, x, y, nb, n))
            if not cands:
                v = _evaluate(b) + bonus - 500.0 * len(rest)
                if v > state["val"]:
                    state["val"], state["first"] = v, first
                return
            cands.sort(key=lambda c: -c[0])
            for _, i, x, y, nb, n in cands[: self.BEAM]:
                rec(nb, [j for j in rest if j != i], first or (i, x, y), bonus + 40.0 * n * n)

        rec(board, idxs, None, 0.0)
        first = state["first"]
        return first if first in set(actions) else actions[0]
