"""
Polityka przeżycia: beam po kolejnościach i położeniach klocków z tacki,
na bitboardach (bit = 8*y + x). Bez wag. Ocena planszy liczy, ile z 41 póz
klocków jeszcze się mieści, karze izolowane dziury i poszarpanie.
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_LINES = _ROWS + _COLS
_NOT_LEFT = _FULL & ~_COLS[0]
_NOT_RIGHT = _FULL & ~_COLS[7]


def _piece_masks(piece):
    """[(x, y, maska)] wszystkich położeń klocka na pustej planszy."""
    h, w = len(piece.shape), len(piece.shape[0])
    base = 0
    for dy, row in enumerate(piece.shape):
        for dx, cell in enumerate(row):
            if cell:
                base |= 1 << (8 * dy + dx)
    return [(x, y, base << (8 * y + x))
            for y in range(8 - h + 1) for x in range(8 - w + 1)]


_MASKS = {p.index: _piece_masks(p) for p in PIECE_POOL}
_PROBES = [[m for _, _, m in _MASKS[p.index]] for p in PIECE_POOL]


def _clear(board):
    full = [m for m in _LINES if board & m == m]
    for m in full:
        board &= ~m
    return board, len(full)


def _popcount(v):
    return bin(v).count("1")


def _eval(board):
    empty = 64 - _popcount(board)
    e = ~board & _FULL
    reach = ((e << 1) & _NOT_LEFT) | ((e >> 1) & _NOT_RIGHT) | (e << 8) | (e >> 8)
    isolated = _popcount(e & ~reach & _FULL)
    trans = _popcount((board ^ (board >> 1)) & _NOT_RIGHT)
    trans += _popcount((board ^ (board >> 8)) & (_FULL >> 8))
    fit = 0
    for masks in _PROBES:
        for m in masks:
            if not board & m:
                fit += 1
                break
    return 4.0 * fit + empty - 2.0 * isolated - trans


def _score(board, lines, rest, pieces):
    s = _eval(board) + 6.0 * lines
    if board == 0:
        s += 50
    for i in rest:
        if all(board & m for _, _, m in _MASKS[pieces[i].index]):
            s -= 200
    return s


_rng = random.Random(12345)
_TRAYS = [tuple(PIECE_POOL[_rng.choice(_rng.choice(PIECE_TYPES))].index for _ in range(3))
          for _ in range(10)]


def _placeable(board, pids):
    """Czy da się postawić wszystkie klocki w jakiejś kolejności (z czyszczeniem linii)."""
    if not pids:
        return True
    for k, pid in enumerate(pids):
        rest = pids[:k] + pids[k + 1:]
        for _, _, m in _MASKS[pid]:
            if not board & m and _placeable(_clear(board | m)[0], rest):
                return True
    return False


def _risk(board):
    """Ułamek próbnych tacek następnej rundy, których nie da się w całości postawić."""
    return sum(not _placeable(board, t) for t in _TRAYS) / len(_TRAYS)


class SearchPolicy:
    name = "search"
    BEAM = 10

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        board = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    board |= 1 << (8 * y + x)
        pieces = game.pieces
        idxs = tuple(i for i, p in enumerate(pieces) if p is not None)
        states = [(0.0, board, idxs, None, 0)]
        for _ in range(len(idxs)):
            nxt = []
            for _, b, rem, first, lines in states:
                for i in rem:
                    rest = tuple(j for j in rem if j != i)
                    for x, y, m in _MASKS[pieces[i].index]:
                        if b & m:
                            continue
                        nb, n = _clear(b | m)
                        nxt.append((_score(nb, lines + n, rest, pieces), nb, rest,
                                    first or (i, x, y), lines + n))
            if not nxt:
                break
            nxt.sort(key=lambda s: -s[0])
            seen, states = set(), []
            for s in nxt:
                k = (s[1], s[2], s[3])
                if k not in seen:
                    seen.add(k)
                    states.append(s)
                    if len(states) == self.BEAM:
                        break
        if len(states) > 1 and not states[0][2]:
            states = sorted(states[:6], key=lambda s: -(s[0] - 150.0 * _risk(s[1])))
        first = states[0][3]
        return first if first is not None else actions[0]
