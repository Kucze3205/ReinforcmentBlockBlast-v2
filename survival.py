"""
Polityka przeżycia: wiązka po tacce na bitboardach z ryzykiem następnej tacki.

Plansza to 64-bitowa liczba (bit = 8*y + x). Cała tacka jest planowana naraz
(wszystkie kolejności i położenia, wiązka po ocenie układu), a najlepsze końcowe
plansze są dodatkowo karane za ułamek losowych następnych tacek, których nie da się ułożyć.
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

_FULL = (1 << 64) - 1
_ROWS = [0xFF << (8 * r) for r in range(8)]
_COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
_LINES = _ROWS + _COLS
_COL0 = 0x0101010101010101
_COL7 = 0x8080808080808080


def _pose_placements(piece):
    out = []
    h, w = len(piece.shape), len(piece.shape[0])
    for y in range(8 - h + 1):
        for x in range(8 - w + 1):
            m = 0
            for dy, row in enumerate(piece.shape):
                for dx, cell in enumerate(row):
                    if cell:
                        m |= 1 << (8 * (y + dy) + x + dx)
            out.append((m, x, y))
    return out


_SQ3 = None
_PLACEMENTS = [_pose_placements(p) for p in PIECE_POOL]


def _clear(board):
    """Czyści pełne linie; zwraca (plansza, liczba linii)."""
    clr = 0
    n = 0
    for ln in _LINES:
        if board & ln == ln:
            clr |= ln
            n += 1
    return board & ~clr, n


def _moves(board, pose):
    return [(m, x, y) for m, x, y in _PLACEMENTS[pose] if not board & m]


def _type_playable(board, t):
    for pose in PIECE_TYPES[t]:
        for m, _, _ in _PLACEMENTS[pose]:
            if not board & m:
                return True
    return False


def _tray_solvable(board, types):
    """Czy tackę (listę typów) da się wstawić w jakiejś kolejności, z czyszczeniem linii."""
    if not types:
        return True
    seen = set()
    for i, t in enumerate(types):
        if t in seen:
            continue
        seen.add(t)
        rest = types[:i] + types[i + 1:]
        for pose in PIECE_TYPES[t]:
            for m, _, _ in _PLACEMENTS[pose]:
                if board & m:
                    continue
                nb, _ = _clear(board | m)
                if _tray_solvable(nb, rest):
                    return True
    return False


def _eval(board):
    """Niższa = lepsza plansza (heurystyka układu)."""
    filled = bin(board).count("1")
    empty = ~board & _FULL
    up = ((board << 8) & _FULL) | 0xFF
    down = (board >> 8) | (0xFF << 56)
    left = ((board << 1) & _FULL & ~_COL0) | _COL0
    right = ((board >> 1) & ~_COL7) | _COL7
    iso = bin(empty & up & down & left & right).count("1")
    trans = 0
    for r in range(8):
        row = (board >> (8 * r)) & 0xFF
        trans += bin((row ^ (row >> 1)) & 0x7F).count("1")
    for c in range(8):
        v = 0
        for r in range(8):
            v |= ((board >> (8 * r + c)) & 1) << r
        trans += bin((v ^ (v >> 1)) & 0x7F).count("1")
    fit = 0
    for t in range(15):
        n = 0
        for pose in PIECE_TYPES[t]:
            for m, _, _ in _PLACEMENTS[pose]:
                if not board & m:
                    n += 1
                    if n >= 4:
                        break
            if n >= 4:
                break
        fit += n if n else -5 * 8
    sq = 0
    for m, _, _ in _SQ3:
        if not board & m:
            sq += 1
    return filled * 1.0 + iso * 6.0 + trans * 0.8 - fit * 0.6 - min(sq, 8) * 3.0


def _hard_trays(hard):
    """Multizbiory trójek trudnych typów z wagą = liczba uporządkowanych trójek (z 125)."""
    out = []
    for a in range(len(hard)):
        for b in range(a, len(hard)):
            for c in range(b, len(hard)):
                k = len({a, b, c})
                out.append(((hard[a], hard[b], hard[c]), {3: 6, 2: 3, 1: 1}[k]))
    return out


_SQ3 = _PLACEMENTS[[p.index for p in PIECE_POOL if len(p.shape) == 3 and len(p.shape[0]) == 3 and all(all(r) for r in p.shape)][0]]
_HARD_TRAYS = _hard_trays((3, 4, 6, 7, 10))


class SurvivalPolicy:
    name = "survival"
    BEAM = 100
    FINAL = 10
    HARD = (3, 4, 6, 7, 10)  # beam4, beam5, rect23, square3, corner5
    RISK_W = 400.0

    def __init__(self):
        self.reset(0)

    def reset(self, game_seed):
        self.plan = []
        self.rng = random.Random(f"surv:{game_seed}")

    def act(self, game, actions):
        if self.plan:
            a = self.plan.pop(0)
            if a in actions:
                return a
            self.plan = []
        self.plan = self._search(game) or []
        if self.plan:
            a = self.plan.pop(0)
            if a in actions:
                return a
        self.plan = []
        return actions[0]

    def _search(self, game):
        items = [(i, p.index) for i, p in enumerate(game.pieces) if p is not None]
        board = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    board |= 1 << (8 * y + x)
        beam = [(0.0, board, frozenset(), [])]
        for _ in range(len(items)):
            nxt = {}
            for _, b, used, seq in beam:
                for i, pose in items:
                    if i in used:
                        continue
                    for m, x, y in _moves(b, pose):
                        nb, n = _clear(b | m)
                        key = (nb, used | {i})
                        if key in nxt:
                            continue
                        nxt[key] = (_eval(nb) - 8.0 * n, nb, used | {i}, seq + [(i, x, y)])
            if not nxt:
                break
            beam = sorted(nxt.values(), key=lambda e: e[0])[: self.BEAM]
        maxlen = max(len(e[3]) for e in beam)
        beam = [e for e in beam if len(e[3]) == maxlen]
        best, best_s = None, None
        for s, b, _, seq in beam[: self.FINAL]:
            risk = sum(w for t, w in _HARD_TRAYS if not _tray_solvable(b, list(t))) / 125.0
            s += self.RISK_W * risk
            if best_s is None or s < best_s:
                best, best_s = seq, s
        return best
