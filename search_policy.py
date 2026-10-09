"""
Polityka przeżycia: beam po kolejnościach i położeniach klocków z tacki,
na bitboardach (bit = 8*y + x). Bez wag. Ocena planszy liczy, ile z 41 póz
klocków jeszcze się mieści, karze izolowane dziury i poszarpanie.
"""
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
# prawdopodobieństwo wylosowania pozy: 1/15 na typ, potem 1/n na orientację
_W = [0.0] * len(PIECE_POOL)
for _t in PIECE_TYPES:
    for _i in _t:
        _W[_i] = 1.0 / (len(PIECE_TYPES) * len(_t))


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
    fit = 0.0
    spots = 0
    for w, masks in zip(_W, _PROBES):
        n = 0
        for m in masks:
            if not board & m:
                n += 1
        if n:
            fit += w
            spots += w * min(n, 6)
    return 120.0 * fit + 12.0 * spots + empty - 2.0 * isolated - trans


def _score(board, lines, rest, pieces):
    s = _eval(board) + 6.0 * lines
    if board == 0:
        s += 50
    for i in rest:
        if all(board & m for _, _, m in _MASKS[pieces[i].index]):
            s -= 200
    return s


class SearchPolicy:
    name = "search"
    BEAM = 12

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
        first = states[0][3]
        return first if first is not None else actions[0]
