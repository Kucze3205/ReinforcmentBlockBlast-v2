"""
Polityka przeżycia: wiązka po tacce na bitboardach (bit = wiersz*8 + kolumna).

Przeszukuje kolejności i położenia klocków z bieżącej tacki, tanio ocenia
plansze, a najlepsze liście ocenia drogo: ryzyko, że losowa następna tacka
nie da się w całości postawić (to jedyny sposób przegranej).
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
C0 = 0x0101010101010101           # kolumna 0 (i mnożnik wierszy/kolumn)
COL7 = C0 << 7
ROW0 = 0xFF
ROW7 = 0xFF << 56
NC0 = FULL ^ C0
NC7 = FULL ^ COL7
NROW7 = FULL ^ ROW7

MASKS = []
for _p in PIECE_POOL:
    h, w = len(_p.shape), len(_p.shape[0])
    ms = []
    for y in range(8 - h + 1):
        for x in range(8 - w + 1):
            m = 0
            for dy, row in enumerate(_p.shape):
                for dx, c in enumerate(row):
                    if c:
                        m |= 1 << ((y + dy) * 8 + x + dx)
            ms.append((m, x, y))
    MASKS.append(ms)
BARE = [[m for m, _, _ in ms] for ms in MASKS]


def clear(b):
    x = b
    x &= x >> 1
    x &= x >> 2
    x &= x >> 4
    rf = x & C0
    y = b & (b >> 8)
    y &= y >> 16
    y &= y >> 32
    cf = y & 255
    if rf or cf:
        b &= FULL ^ (rf * 255 | cf * C0)
    return b


W_POP, W_HOLE, W_POCK, W_TRANS = 1.0, 6.0, 1.5, 0.6
W_SQ, W_BEAM = 6.0, 4.0
START3 = sum(0b00111111 << (8 * r) for r in range(8))
START5 = sum(0b00001111 << (8 * r) for r in range(8))


def cheap(b):
    e = FULL ^ b
    L = ((b << 1) & NC0 & FULL) | C0
    R = ((b >> 1) & NC7) | COL7
    U = ((b << 8) & FULL) | ROW0
    D = (b >> 8) | ROW7
    hole = (e & L & R & U & D).bit_count()
    pock = (e & ((L & R) | (U & D))).bit_count()
    trans = ((b ^ (b >> 1)) & NC7).bit_count() + ((b ^ (b >> 8)) & NROW7).bit_count()
    h3 = e & (e >> 1) & (e >> 2) & START3
    sq = (h3 & (h3 >> 8) & (h3 >> 16)).bit_count()
    v3 = e & (e >> 8) & (e >> 16)
    h5 = (h3 & (e >> 3) & (e >> 4) & START5).bit_count()
    v5 = (v3 & (e >> 24) & (e >> 32)).bit_count()
    room = -W_SQ * (3 - min(sq, 3)) - W_BEAM * ((h5 == 0) + (v5 == 0))
    return room - (W_POP * b.bit_count() + W_HOLE * hole + W_POCK * pock + W_TRANS * trans)


def playable(b, ps, budget=400):
    """Czy da się postawić wszystkie klocki ps (w dowolnej kolejności)? Przy wyczerpaniu budżetu: tak."""
    seen = set()
    nodes = [0]

    def rec(b, rem):
        if not rem:
            return True
        key = (b, rem)
        if key in seen:
            return False
        seen.add(key)
        for i, p in enumerate(ps):
            bit = 1 << i
            if not rem & bit:
                continue
            for m in BARE[p]:
                if not m & b:
                    nodes[0] += 1
                    if nodes[0] > budget:
                        return True
                    if rec(clear(b | m), rem ^ bit):
                        return True
        return False

    return rec(b, (1 << len(ps)) - 1)


class SurvivalPolicy:
    name = "survival"

    def __init__(self, beam=40, final=10, final_crowded=24, trays=24, risk_w=60.0):
        self.beam, self.final, self.final_crowded = beam, final, final_crowded
        self.trays, self.risk_w = trays, risk_w

    def reset(self, game_seed):
        self.rng = random.Random(f"surv:{game_seed}")

    def _risk(self, b):
        rng, bad = self.rng, 0
        for _ in range(self.trays):
            ps = [rng.choice(PIECE_TYPES[rng.randrange(15)]) for _ in range(3)]
            if not playable(b, ps):
                bad += 1
        return bad / self.trays

    def act(self, game, actions):
        grid = game.board.grid
        b = 0
        for r in range(8):
            for c in range(8):
                if grid[r][c]:
                    b |= 1 << (r * 8 + c)
        slots = [i for i, p in enumerate(game.pieces) if p is not None]
        full = (1 << len(slots)) - 1
        level = {(b, full): (0.0, None)}
        leaves = []
        for _ in range(len(slots)):
            nxt = {}
            for (bd, rem), (_, first) in level.items():
                for k, s in enumerate(slots):
                    if not rem >> k & 1:
                        continue
                    nrem = rem ^ (1 << k)
                    for m, x, y in MASKS[game.pieces[s].index]:
                        if m & bd:
                            continue
                        nb = clear(bd | m)
                        key = (nb, nrem)
                        if key in nxt:
                            continue
                        nxt[key] = (cheap(nb), first or (s, x, y))
            if not nxt:
                break
            if len(nxt) > self.beam:
                nxt = dict(sorted(nxt.items(), key=lambda kv: -kv[1][0])[: self.beam])
            level = nxt
        else:
            leaves = list(level.items())
        if not leaves:
            return actions[0]
        leaves.sort(key=lambda kv: -kv[1][0])
        crowded = b.bit_count() > 40
        top = leaves[: self.final_crowded if crowded else self.final]
        best, best_s = None, None
        for (bd, _), (sc, first) in top:
            s = sc - self.risk_w * self._risk(bd)
            if best_s is None or s > best_s:
                best, best_s = first, s
        return tuple(best)
