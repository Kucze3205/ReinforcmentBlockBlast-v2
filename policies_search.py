"""Wiązka po tacce na bitboardach z ryzykiem niegrywalnej następnej tacki."""
import random

from pieces import PIECE_POOL, PIECE_TYPES

N = 8
FULL = (1 << 64) - 1
ROWS = [sum(1 << (y * N + x) for x in range(N)) for y in range(N)]
COLS = [sum(1 << (y * N + x) for y in range(N)) for x in range(N)]
LINES = ROWS + COLS


def _pose_masks(piece):
    h, w = len(piece.shape), len(piece.shape[0])
    base = 0
    for dy, row in enumerate(piece.shape):
        for dx, c in enumerate(row):
            if c:
                base |= 1 << (dy * N + dx)
    out = []
    for y in range(N - h + 1):
        for x in range(N - w + 1):
            out.append((base << (y * N + x), x, y))
    return out


POSES = [_pose_masks(p) for p in PIECE_POOL]
POSE_MASKS = [[m for m, _, _ in ps] for ps in POSES]

NEIGH = []
for _i in range(64):
    _y, _x = divmod(_i, N)
    _m = 0
    for _dy, _dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        _yy, _xx = _y + _dy, _x + _dx
        if 0 <= _yy < N and 0 <= _xx < N:
            _m |= 1 << (_yy * N + _xx)
    NEIGH.append(_m)


def place(board, mask):
    """Zwraca (nowa plansza, liczba wyczyszczonych linii)."""
    b = board | mask
    clear = 0
    n = 0
    for lm in LINES:
        if b & lm == lm:
            clear |= lm
            n += 1
    return b & ~clear, n


def playable(board, tray):
    """Czy tacka (krotka indeksów póz) da się w pełni ułożyć w jakiejś kolejności."""
    seen = set()

    def rec(b, rest):
        if not rest:
            return True
        key = (b, rest)
        if key in seen:
            return False
        seen.add(key)
        for i, p in enumerate(rest):
            if p in rest[:i]:
                continue
            sub = rest[:i] + rest[i + 1:]
            for m in POSE_MASKS[p]:
                if b & m == 0:
                    nb, _ = place(b, m)
                    if rec(nb, sub):
                        return True
        return False

    return rec(board, tuple(tray))


W = dict(line=0.0, fill=6.0, iso=15.0, pocket=70.0, trans=22.4, clear=10.0)


def static_eval(board):
    """Wyższe = lepsze: mało zapełnienia, brak kieszeni, gładkie krawędzie."""
    filled = bin(board).count("1")
    empty = ~board & FULL
    iso = 0
    pocket = 0
    e = empty
    while e:
        low = e & -e
        i = low.bit_length() - 1
        e ^= low
        nb = bin(NEIGH[i] & empty).count("1")
        edge = 4 - bin(NEIGH[i]).count("1")
        if nb == 0:
            iso += 1
        elif nb + edge <= 1:
            pocket += 1
    trans = 0
    ln = 0
    for lm in LINES:
        k = bin(board & lm).count('1')
        ln += k * k
    for y in range(N):
        r = (board >> (y * N)) & 0xFF
        trans += bin((r ^ (r >> 1)) & 0x7F).count("1")
    for x in range(N):
        c = 0
        for y in range(N):
            c |= ((board >> (y * N + x)) & 1) << y
        trans += bin((c ^ (c >> 1)) & 0x7F).count("1")
    return W['line'] * ln - (W['fill'] * filled + W['iso'] * iso + W['pocket'] * pocket + W['trans'] * trans)


NC = [bin(ms[0]).count("1") for ms in POSE_MASKS]


def mobility(board):
    """Suma rozmiarów póz, które mieszczą się na planszy (duże liczą się bardziej)."""
    t = 0
    for ms, nc in zip(POSE_MASKS, NC):
        for m in ms:
            if not board & m:
                t += nc
                break
    return t


POSE_W = []
for _t, _idx in enumerate(PIECE_TYPES):
    for _p in _idx:
        POSE_W.append(1.0 / (len(PIECE_TYPES) * len(_idx)))
from itertools import combinations_with_replacement
from math import factorial


def _mult(trip):
    """Liczba uporządkowanych permutacji multizbioru trójki."""
    a, b, c = trip
    if a == b == c:
        return 1
    if a == b or b == c:
        return 3
    return 6


def risk(board, tight_max=8, tight_cnt=10):
    """Prawdopodobieństwo, że losowa następna tacka jest niegrywalna (przybliżone:
    martwe pozy dokładnie, trójki z najciaśniejszych póz po wyliczeniu)."""
    dead_w = 0.0
    tight = []
    for pi, ms in enumerate(POSE_MASKS):
        c = 0
        for m in ms:
            if not board & m:
                c += 1
                if c > tight_cnt:
                    break
        if c == 0:
            dead_w += POSE_W[pi]
        elif c <= tight_cnt:
            tight.append((c, pi))
    tight.sort()
    tight = [pi for _, pi in tight[:tight_max]]
    r = 1.0 - (1.0 - dead_w) ** 3
    for trip in combinations_with_replacement(tight, 3):
        if not playable(board, trip):
            r += _mult(trip) * POSE_W[trip[0]] * POSE_W[trip[1]] * POSE_W[trip[2]]
    return r


class SearchPolicy:
    name = "search"

    def __init__(self, beam=40, final=20, samples=24, risk_w=750.0, mob_w=0.7, seed=0):
        self.mob_w = mob_w
        self.beam, self.final, self.samples = beam, final, samples
        self.risk_w = risk_w
        self._seed = seed
        self.rng = random.Random(seed)

    def reset(self, game_seed):
        self.rng = random.Random(f"{self._seed}:{game_seed}")

    def _sample_tray(self):
        r = self.rng
        return tuple(
            r.choice(PIECE_TYPES[r.randrange(len(PIECE_TYPES))]) for _ in range(3)
        )

    def act(self, game, actions):
        if len(actions) == 1:
            return actions[0]
        pieces = tuple((i, p.index) for i, p in enumerate(game.pieces) if p is not None)
        board0 = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    board0 |= 1 << (y * N + x)
        beam = [(board0, pieces, None, 0.0)]
        leaves = []
        for _ in range(len(pieces)):
            nxt = {}
            for board, rest, first, bonus in beam:
                for k, (slot, pose) in enumerate(rest):
                    sub = rest[:k] + rest[k + 1:]
                    for m, x, y in POSES[pose]:
                        if board & m:
                            continue
                        nb, n = place(board, m)
                        f = first if first is not None else (slot, x, y)
                        bn = bonus + W['clear'] * n * n
                        key = (nb, sub)
                        sc = bn + static_eval(nb)
                        old = nxt.get(key)
                        if old is None or sc > old[0]:
                            nxt[key] = (sc, nb, sub, f, bn)
            if not nxt:
                if not leaves and beam and beam[0][2] is not None:
                    # tacka nie mieści się w całości: najlepszy częściowy pierwszy ruch
                    b = max(beam, key=lambda s: s[3] + static_eval(s[0]))
                    return b[2]
                break
            ranked = sorted(nxt.values(), key=lambda t: -t[0])
            if ranked[0][2]:
                beam = [(b, s, f, bn) for _, b, s, f, bn in ranked[: self.beam]]
            else:
                leaves = ranked
                beam = []
        if not leaves:
            # tacka nie mieści się w całości: weź najlepszy częściowy pierwszy ruch
            return actions[0]
        best, best_s = None, None
        for sc, nb, _, f, bn in leaves[: self.final]:
            s = sc - self.risk_w * risk(nb) + self.mob_w * mobility(nb)
            if best_s is None or s > best_s:
                best, best_s = f, s
        return best


def build(weights=None):
    return SearchPolicy()
