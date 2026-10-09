"""
Polityka przeżycia: przeszukiwanie wiązką po całej tacce.

Sprawdza wszystkie kolejności i pozycje trzech klocków, maksymalizując przeżycie
(mobilność planszy, mało dziur i przejść); punkty działają tylko jako remis.
"""
from itertools import permutations

from pieces import PIECE_POOL

_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_LINES = _ROWS + _COLS


def _piece_masks(piece):
    h, w = len(piece.shape), len(piece.shape[0])
    out = []
    for y in range(8 - h + 1):
        for x in range(8 - w + 1):
            m = 0
            for dy, row in enumerate(piece.shape):
                for dx, c in enumerate(row):
                    if c:
                        m |= 1 << (8 * (y + dy) + x + dx)
            out.append((x, y, m))
    return out


_MASKS = {p.index: _piece_masks(p) for p in PIECE_POOL}


def _pop(v):
    return bin(v).count("1")


def _clear(board):
    n = 0
    clr = 0
    for ln in _LINES:
        if board & ln == ln:
            clr |= ln
            n += 1
    return board & ~clr, n


def _evaluate(board):
    occ = _pop(board)
    fit = 0
    for ms in _MASKS.values():
        for _, _, m in ms:
            if not board & m:
                fit += 1
                break
    holes = 0
    trans = 0
    for r in range(8):
        for c in range(8):
            b = (board >> (8 * r + c)) & 1
            if c < 7 and b != (board >> (8 * r + c + 1)) & 1:
                trans += 1
            if r < 7 and b != (board >> (8 * (r + 1) + c)) & 1:
                trans += 1
            if not b:
                n = 0
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < 8 and 0 <= cc < 8) or (board >> (8 * rr + cc)) & 1:
                        n += 1
                if n >= 3:
                    holes += 1
    return fit * 6.0 - occ - holes * 4.0 - trans * 0.8


class SearchPolicy:
    name = "search"
    BEAM = 12

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        board = 0
        for r, row in enumerate(game.board.grid):
            for c, v in enumerate(row):
                if v:
                    board |= 1 << (8 * r + c)
        idxs = [i for i, p in enumerate(game.pieces) if p is not None]
        best_val, best_act = None, actions[0]
        for perm in permutations(idxs):
            states = [(0.0, board, None)]
            for i in perm:
                pid = game.pieces[i].index
                nxt = []
                for bonus, b, first in states:
                    for x, y, m in _MASKS[pid]:
                        if b & m:
                            continue
                        nb, n = _clear(b | m)
                        gain = bonus + n * 3.0 + (20.0 if nb == 0 else 0.0)
                        nxt.append((gain - _pop(nb), gain, nb, first or (i, x, y)))
                if not nxt:
                    states = []
                    break
                nxt.sort(key=lambda t: -t[0])
                states = [(g, nb, f) for _, g, nb, f in nxt[: self.BEAM]]
            for g, nb, f in states:
                v = g + _evaluate(nb)
                if best_val is None or v > best_val:
                    best_val, best_act = v, f
        return tuple(best_act)
