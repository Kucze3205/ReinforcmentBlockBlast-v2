"""
Polityka przeszukująca całą tackę (bitboard, 64-bitowa plansza).

Dla klocków z tacki sprawdza kolejności i pozycje (z cięciem do najlepszych
kandydatów na każdym poziomie), ocenia planszę heurystyką przeżycia
(dziury, przejścia, zajętość, ruchliwość) i zwraca pierwszy ruch najlepszej
sekwencji. Punkty tylko rozstrzygają remis.
"""
from functools import lru_cache
from itertools import permutations

from board import Board
from pieces import PIECE_POOL

W = 8
FULL = (1 << 64) - 1
ROW_MASKS = [sum(1 << (r * W + c) for c in range(W)) for r in range(W)]
COL_MASKS = [sum(1 << (r * W + c) for r in range(W)) for c in range(W)]

_PLACEMENTS = {}


def placements(idx):
    """Lista (x, y, maska) dla klocka o danym indeksie w puli."""
    if idx not in _PLACEMENTS:
        piece = PIECE_POOL[idx]
        h, w = len(piece.shape), len(piece.shape[0])
        out = []
        for y in range(W - h + 1):
            for x in range(W - w + 1):
                m = 0
                for dy, row in enumerate(piece.shape):
                    for dx, cell in enumerate(row):
                        if cell:
                            m |= 1 << ((y + dy) * W + x + dx)
                out.append((x, y, m))
        _PLACEMENTS[idx] = out
    return _PLACEMENTS[idx]


def apply(board, mask):
    """Stawia maskę i czyści linie. Zwraca (plansza, liczba linii)."""
    b = board | mask
    clear = 0
    lines = 0
    for rm in ROW_MASKS:
        if b & rm == rm:
            clear |= rm
            lines += 1
    for cm in COL_MASKS:
        if b & cm == cm:
            clear |= cm
            lines += 1
    return b & ~clear & FULL, lines


def _popcount(x):
    return bin(x).count("1")


@lru_cache(maxsize=1 << 20)
def evaluate(b):
    """Im wyżej tym lepiej. Heurystyka przeżycia."""
    if b == 0:
        return 1000.0
    occ = _popcount(b)
    score = -1.0 * occ
    # komórki puste otoczone (dziury): liczba sąsiadów zajętych/ścian
    empty = ~b & FULL
    holes = 0
    for i in range(64):
        if empty >> i & 1:
            r, c = divmod(i, W)
            n = 0
            n += 1 if r == 0 or b >> (i - W) & 1 else 0
            n += 1 if r == W - 1 or b >> (i + W) & 1 else 0
            n += 1 if c == 0 or b >> (i - 1) & 1 else 0
            n += 1 if c == W - 1 or b >> (i + 1) & 1 else 0
            if n == 4:
                holes += 3
            elif n == 3:
                holes += 1
    score -= 4.0 * holes
    # przejścia wierszy i kolumn (poszarpanie)
    trans = 0
    for r in range(W):
        row = (b >> (r * W)) & 0xFF
        trans += _popcount((row ^ (row >> 1)) & 0x7F)
    for c in range(W):
        col = 0
        for r in range(W):
            col |= (b >> (r * W + c) & 1) << r
        trans += _popcount((col ^ (col >> 1)) & 0x7F)
    score -= 0.7 * trans
    # linie prawie pełne to potencjał
    for m in ROW_MASKS + COL_MASKS:
        k = _popcount(b & m)
        if k >= 6:
            score += (k - 5) * 1.5
    return score


class SearchPolicy:
    name = "search"
    BEAM = 8

    def reset(self, game_seed):
        pass

    def _chain(self, board, key, depth):
        if depth == len(key):
            return evaluate(board)
        cands = []
        for x, y, m in placements(key[depth]):
            if board & m:
                continue
            nb, lines = apply(board, m)
            cands.append((evaluate(nb) + 6.0 * lines, nb))
        if not cands:
            return None
        cands.sort(key=lambda t: -t[0])
        best = None
        for _, nb in cands[: self.BEAM]:
            v = self._chain(nb, key, depth + 1)
            if v is not None and (best is None or v > best):
                best = v
        return best

    def act(self, game, actions):
        board = 0
        for r, row in enumerate(game.board.grid):
            for c, v in enumerate(row):
                if v:
                    board |= 1 << (r * W + c)
        idxs = [(i, p.index) for i, p in enumerate(game.pieces) if p is not None]
        best_action, best_val = actions[0], None
        for action in actions:
            i, x, y = action
            pidx = game.pieces[i].index
            mask = next(m for px, py, m in placements(pidx) if px == x and py == y)
            nb, lines = apply(board, mask)
            rest = tuple(p for j, p in idxs if j != i)
            if rest:
                val = self._search_rest(nb, rest)
                if val is None:
                    val = -1e6  # ruch kończy partię
            else:
                val = evaluate(nb)
            val += 6.0 * lines + 0.01 * (game.pieces[i] and sum(map(sum, game.pieces[i].shape)))
            if best_val is None or val > best_val:
                best_action, best_val = action, val
        return best_action

    def _search_rest(self, board, rest):
        best = None
        seen = set()
        for order in permutations(rest):
            if order in seen:
                continue
            seen.add(order)
            v = self._chain(board, order, 0)
            if v is not None and (best is None or v > best):
                best = v
        return best
