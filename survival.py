"""Polityka przeżycia: wiązka po tacce na bitboardach (bit y*8+x)."""
from pieces import PIECE_POOL, PIECE_TYPES

W = 8
ROWS = [sum(1 << (y * W + x) for x in range(W)) for y in range(W)]
COLS = [sum(1 << (y * W + x) for y in range(W)) for x in range(W)]

# Maski położeń (maska, x, y) i liczba komórek dla każdej pozy.
MASKS = []
for _p in PIECE_POOL:
    _h, _w = len(_p.shape), len(_p.shape[0])
    _cells = [(dy, dx) for dy in range(_h) for dx in range(_w) if _p.shape[dy][dx]]
    _lst = []
    for _y in range(W - _h + 1):
        for _x in range(W - _w + 1):
            _lst.append((sum(1 << ((_y + dy) * W + _x + dx) for dy, dx in _cells), _x, _y))
    MASKS.append((_lst, len(_cells)))

# Prawdopodobieństwo wylosowania pozy: 1/15 na typ, potem 1/n na orientację.
PROB = [0.0] * len(PIECE_POOL)
for _idxs in PIECE_TYPES:
    for _i in _idxs:
        PROB[_i] = 1.0 / (15 * len(_idxs))

UNFIT_W = 400.0
BEAM = 40
FINAL = 12


def clear(b):
    """Zwraca (plansza po czyszczeniu, liczba linii)."""
    m = 0
    n = 0
    for r in ROWS:
        if b & r == r:
            m |= r
            n += 1
    for c in COLS:
        if b & c == c:
            m |= c
            n += 1
    return b & ~m, n


def to_bits(grid):
    b = 0
    for y in range(W):
        for x in range(W):
            if grid[y][x]:
                b |= 1 << (y * W + x)
    return b


def unfit_mass(b):
    """Prawdopodobieństwo, że losowa poza nie ma na planszy żadnego położenia."""
    u = 0.0
    for i, (lst, _) in enumerate(MASKS):
        for m, _, _ in lst:
            if not b & m:
                break
        else:
            u += PROB[i]
    return u


def holes(b):
    """Puste pola otoczone zajętymi (lub ścianą) ze wszystkich 4 stron."""
    n = 0
    for y in range(W):
        for x in range(W):
            i = y * W + x
            if b >> i & 1:
                continue
            if ((x == 0 or b >> (i - 1) & 1) and (x == W - 1 or b >> (i + 1) & 1)
                    and (y == 0 or b >> (i - W) & 1) and (y == W - 1 or b >> (i + W) & 1)):
                n += 1
    return n


def transitions(b):
    t = 0
    for y in range(W):
        row = (b >> (y * W)) & 255
        t += bin((row ^ (row >> 1)) & 127).count("1") + (row & 1) + (row >> 7)
    for x in range(W):
        col = 0
        for y in range(W):
            col |= (b >> (y * W + x) & 1) << y
        t += bin((col ^ (col >> 1)) & 127).count("1") + (col & 1) + (col >> 7)
    return t


def cheap(b, gain):
    return -bin(b).count("1") - holes(b) * 6 - transitions(b) * 0.5 + gain * 0.05


class SurvivalPolicy:
    def reset(self, seed):
        pass

    def act(self, game, actions):
        pieces = [(i, p) for i, p in enumerate(game.pieces) if p is not None]
        # stan: (bitboard, użyte, pierwsza akcja, zysk)
        level = [(to_bits(game.board.grid), 0, None, 0)]
        for _ in pieces:
            nxt = {}
            for b, used, first, gain in level:
                for k, (idx, p) in enumerate(pieces):
                    if used >> k & 1:
                        continue
                    lst, cells = MASKS[p.index]
                    for m, x, y in lst:
                        if b & m:
                            continue
                        nb, n = clear(b | m)
                        g = gain + cells + (10 * n * n if n else 0)
                        if not nb:
                            g += 300
                        key = (nb, used | 1 << k)
                        s = cheap(nb, g)
                        if key not in nxt or nxt[key][0] < s:
                            nxt[key] = (s, nb, used | 1 << k, first or (idx, x, y), g)
            if not nxt:
                break
            ranked = sorted(nxt.values(), key=lambda t: -t[0])[:BEAM]
            level = [r[1:] for r in ranked]
        if level[0][2] is None:
            return actions[0]
        top = level[:FINAL]
        best = max(top, key=lambda s: cheap(s[0], s[3]) - unfit_mass(s[0]) * UNFIT_W)
        return best[2]


def build(weights=None):
    return SurvivalPolicy()
