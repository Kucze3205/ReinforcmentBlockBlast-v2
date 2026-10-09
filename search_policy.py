"""
Polityka przeżycia: wiązka po całej tacce na bitboardach (plansza 8x8 = 64 bity)
z oceną planszy uwzględniającą ryzyko następnej tacki (rozkład generatora).
"""
from pieces import PIECE_POOL, PIECE_TYPES

ROWM = [0xFF << (8 * r) for r in range(8)]
COLM = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]
BEAM = 24
W = {"trans": 3.0, "fit": 2.0, "dead": 400.0, "empty": 0.3, "gain": 0.01}


def _pose_masks(piece):
    h, w = len(piece.shape), len(piece.shape[0])
    base = 0
    for dy, row in enumerate(piece.shape):
        for dx, c in enumerate(row):
            if c:
                base |= 1 << (8 * dy + dx)
    return [(base << (8 * y + x), x, y)
            for y in range(9 - h) for x in range(9 - w)]


_MASKS = {p.index: _pose_masks(p) for p in PIECE_POOL}
_TYPE_POSES = [list(t) for t in PIECE_TYPES]


def _clear(b):
    """Zwraca (plansza po czyszczeniu, liczba pełnych linii)."""
    full, n = 0, 0
    for m in ROWM + COLM:
        if b & m == m:
            full |= m
            n += 1
    return b & ~full, n


def _fits(b, idx):
    for m, _, _ in _MASKS[idx]:
        if not b & m:
            return True
    return False


def _eval(b):
    dead = 0
    fit = 0.0
    for poses in _TYPE_POSES:
        ok = sum(1 for i in poses if _fits(b, i))
        if ok == 0:
            dead += 1
        fit += ok / len(poses)
    trans = 0
    for r in range(8):
        row = (b >> (8 * r)) & 0xFF
        trans += bin((row ^ (row >> 1)) & 0x7F).count("1")
    for c in range(8):
        col = [(b >> (8 * r + c)) & 1 for r in range(8)]
        trans += sum(col[i] != col[i + 1] for i in range(7))
    return (-W["dead"] * dead + W["fit"] * fit - W["trans"] * trans
            - W["empty"] * bin(b).count("1"))


class SearchPolicy:
    name = "search"

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        board = 0
        for y, row in enumerate(game.board.grid):
            for x, v in enumerate(row):
                if v:
                    board |= 1 << (8 * y + x)
        rem = tuple(i for i, p in enumerate(game.pieces) if p is not None)
        layer = [(board, None, 0.0, rem)]
        final = None
        for depth in range(len(rem)):
            scored = []
            for b, first, sc, left in layer:
                for k in left:
                    rest = tuple(j for j in left if j != k)
                    for m, x, y in _MASKS[game.pieces[k].index]:
                        if b & m:
                            continue
                        nb, n = _clear(b | m)
                        gain = (bin(m).count("1") + 40 * n * n
                                + (300 if nb == 0 else 0))
                        s = sc + W["gain"] * gain
                        scored.append((s + _eval(nb), nb, first or (k, x, y), s, rest))
            if not scored:
                break
            scored.sort(key=lambda t: -t[0])
            final = scored[0][2]
            seen, layer = set(), []
            for tot, nb, f, s, rest in scored:
                if (nb, rest) in seen:
                    continue
                seen.add((nb, rest))
                layer.append((nb, f, s, rest))
                if len(layer) >= BEAM:
                    break
        if final is not None and tuple(final) in set(actions):
            return tuple(final)
        return actions[0]
