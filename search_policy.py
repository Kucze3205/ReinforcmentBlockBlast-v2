"""
Polityka przeżycia: beam po kolejnościach i położeniach klocków z tacki,
na bitboardach (bit = 8*y + x). Bez wag. Ocena planszy liczy, ile z 41 póz
klocków jeszcze się mieści, karze izolowane dziury i poszarpanie.
"""
import random
from functools import lru_cache

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


@lru_cache(maxsize=1 << 18)
def _eval(board):
    empty = 64 - _popcount(board)
    e = ~board & _FULL
    reach = ((e << 1) & _NOT_LEFT) | ((e >> 1) & _NOT_RIGHT) | (e << 8) | (e >> 8)
    isolated = _popcount(e & ~reach & _FULL)
    trans = _popcount((board ^ (board >> 1)) & _NOT_RIGHT)
    trans += _popcount((board ^ (board >> 8)) & (_FULL >> 8))
    fit = 0
    for masks in _PROBES:
        c = 0
        for m in masks:
            if not board & m:
                c += 1
                if c == 3:
                    break
        fit += c
    return 1.5 * fit + empty - 2.0 * isolated - trans


def _score(board, lines, rest, pieces):
    s = _eval(board) + 6.0 * lines
    if board == 0:
        s += 50
    for i in rest:
        if all(board & m for _, _, m in _MASKS[pieces[i].index]):
            s -= 200
    return s


_POSE_W = [(p, 1.0 / (len(PIECE_TYPES) * len(ts)))
           for ts in PIECE_TYPES for p in ts]


@lru_cache(maxsize=1 << 17)
def _next_tray(board):
    """Oczekiwana wartość po postawieniu jednego losowego klocka (rozkład generatora)."""
    tot = 0.0
    for pi, w in _POSE_W:
        best = None
        for _, _, m in _MASKS[pi]:
            if board & m:
                continue
            nb, n = _clear(board | m)
            v = _eval(nb) + 6.0 * n
            if best is None or v > best:
                best = v
        tot += w * (best if best is not None else -300.0)
    return tot


def _tray_value(board, tray, beam=3):
    """Ocena po zagraniu całej tacki 3 klocków (mały beam); brak miejsca = -300 za klocek."""
    states = [(0.0, board, tuple(range(len(tray))))]
    for _ in range(len(tray)):
        nxt = {}
        for _, b, rem in states:
            for i in rem:
                rest = tuple(j for j in rem if j != i)
                for _, _, m in _MASKS[tray[i].index]:
                    if b & m:
                        continue
                    nb, n = _clear(b | m)
                    k = (nb, rest)
                    if k not in nxt:
                        nxt[k] = (_eval(nb) + 6.0 * n, nb, rest)
        if not nxt:
            return -300.0 * len(rem) + max(t[0] for t in states)
        states = sorted(nxt.values(), key=lambda t: -t[0])[:beam]
    return states[0][0]


class SearchPolicy:
    name = "search"
    BEAM = 40
    LOOK = 5
    LOOK_W = 1.0
    TRAYS = 3
    TRAY_W = 1.0

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
        if not states[0][2]:
            rng = random.Random(board)
            trays = [[PIECE_POOL[rng.choice(rng.choice(PIECE_TYPES))] for _ in range(3)]
                     for _ in range(self.TRAYS)]
            top = []
            for s in states[: self.LOOK]:
                tv = sum(_tray_value(s[1], t) for t in trays) / len(trays)
                top.append((s[0] + self.LOOK_W * _next_tray(s[1]) + self.TRAY_W * tv, s))
            states = [max(top, key=lambda t: t[0])[1]]
        first = states[0][3]
        return first if first is not None else actions[0]
