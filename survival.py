"""
Polityka przeżycia: wiązka po tacce na bitboardach + szacunek ryzyka następnej tacki.

Plansza to 64-bitowa liczba (bit y*8+x). Cel to nieprzegrywanie, więc punkty się nie liczą:
wiązka układa całą tackę (3 klocki, dowolna kolejność), a koszt liści obejmuje szacunek
prawdopodobieństwa, że losowa następna tacka będzie niegrywalna.
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
COL0 = 0x0101010101010101
COL7 = COL0 << 7
BEAM = 24
FINAL = 10
RISK_SAMPLES = 40
RISK_W = 600.0
TRANS_W = 1.0
ISO_W = 8.0
FREE_W = 1.5
MOB_W = 15.0
HARD_TYPES = (3, 4, 6, 7, 10)  # beam4, beam5, rect23, square3, corner5


def _build_tables():
    places = []
    for p in PIECE_POOL:
        h, w = len(p.shape), len(p.shape[0])
        lst = []
        for y in range(8 - h + 1):
            for x in range(8 - w + 1):
                m = 0
                for dy, row in enumerate(p.shape):
                    for dx, c in enumerate(row):
                        if c:
                            m |= 1 << ((y + dy) * 8 + x + dx)
                lst.append((m, x, y))
        places.append(lst)
    return places


_PLACES = _build_tables()
_MASKS = [[m for m, _, _ in lst] for lst in _PLACES]


def _clear(b):
    t = b & (b >> 1)
    t &= t >> 2
    t &= t >> 4
    rows = t & COL0
    c = b & (b >> 8)
    c &= c >> 16
    c &= c >> 32
    c &= 255
    if not rows and not c:
        return b
    return b & ~((rows * 255) | (c * COL0))


def _cheap(b):
    free = 64 - b.bit_count()
    trans = ((b ^ (b >> 1)) & ~COL7).bit_count() + ((b ^ (b >> 8)) & 0x00FFFFFFFFFFFFFF).bit_count()
    e = ~b & FULL
    nb = (((e << 1) & ~COL0) | ((e >> 1) & ~COL7) | (e << 8) | (e >> 8)) & FULL
    iso = (e & ~nb).bit_count()
    return TRANS_W * trans + ISO_W * iso - FREE_W * free


def _small_regions(b):
    """Puste pola w obszarach mniejszych niż 3 pola (trudne do zagospodarowania)."""
    e = ~b & FULL
    total = 0
    while e:
        reg = e & -e
        while True:
            n = (reg | ((reg << 1) & ~COL0) | ((reg >> 1) & ~COL7) | (reg << 8) | (reg >> 8)) & e
            if n == reg:
                break
            reg = n
        sz = reg.bit_count()
        if sz < 3:
            total += sz
        e &= ~reg
    return total


def _playable(b, pcs):
    """Czy da się postawić wszystkie klocki z krotki pcs (indeksy poz) w jakiejś kolejności."""
    if not pcs:
        return True
    seen = set()
    for i, p in enumerate(pcs):
        if p in seen:
            continue
        seen.add(p)
        rest = pcs[:i] + pcs[i + 1:]
        for m in _MASKS[p]:
            if not (b & m) and _playable(_clear(b | m), rest):
                return True
    return False


def _count_fit(b, p):
    n = 0
    for m in _MASKS[p]:
        if not (b & m):
            n += 1
    return n


class SearchPolicy:
    name = "search"

    def reset(self, game_seed):
        self.rng = random.Random(f"risk:{game_seed}")
        self.plan = []

    @staticmethod
    def _board_bits(game):
        b = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b |= 1 << (y * 8 + x)
        return b

    def _risk_trays(self):
        rng = self.rng
        trays, weights = [], []
        for _ in range(RISK_SAMPLES):
            tray, w = [], 1.0
            for _ in range(3):
                t = rng.randrange(15) if rng.random() < 0.5 else rng.choice(HARD_TYPES)
                n = len(PIECE_TYPES[t])
                pose = PIECE_TYPES[t][rng.randrange(n)]
                nat = 1.0 / (15 * n)
                prop = 0.5 * nat + (0.5 / len(HARD_TYPES) / n if t in HARD_TYPES else 0.0)
                w *= nat / prop
                tray.append(pose)
            trays.append(tuple(tray))
            weights.append(w)
        return trays, weights

    def _risk(self, b, trays, weights):
        bad = tot = 0.0
        for tr, w in zip(trays, weights):
            tot += w
            if not _playable(b, tr):
                bad += w
        return bad / tot

    def _search(self, b, poses):
        level = {(b, 7): (0.0, ())}
        leaves = []
        for depth in range(3):
            nxt = {}
            for (bd, rem), (_, path) in level.items():
                moved = False
                for s in range(3):
                    if not rem & (1 << s) or poses[s] is None:
                        continue
                    for m, x, y in _PLACES[poses[s]]:
                        if bd & m:
                            continue
                        moved = True
                        nb = _clear(bd | m)
                        key = (nb, rem & ~(1 << s))
                        if key not in nxt:
                            nxt[key] = (_cheap(nb), path + ((s, x, y),))
                if not moved and rem:
                    leaves.append((1e6 * (3 - depth), bd, path))
            if not nxt:
                level = {}
                break
            items = sorted(nxt.items(), key=lambda kv: kv[1][0])
            level = dict(items[:BEAM] if depth < 2 else items)
        leaves.extend((cost, bd, path) for (bd, _), (cost, path) in level.items())
        leaves.sort(key=lambda t: t[0])
        if not leaves or leaves[0][0] >= 1e6:
            return leaves[0][2] if leaves else None
        trays, weights = self._risk_trays()
        best, best_cost = None, None
        for cost, bd, path in leaves[:FINAL]:
            if cost >= 1e6:
                continue
            c = cost + RISK_W * self._risk(bd, trays, weights) + 6.0 * _small_regions(bd)
            c += MOB_W * sum(1.0 / (1 + _count_fit(bd, p)) for p in range(len(_MASKS)))
            if best_cost is None or c < best_cost:
                best, best_cost = path, c
        return best

    def act(self, game, actions):
        if self.plan and self.plan[0] in actions:
            return self.plan.pop(0)
        self.plan = []
        poses = [p.index if p else None for p in game.pieces]
        path = self._search(self._board_bits(game), poses)
        if path and tuple(path[0]) in actions:
            self.plan = [tuple(a) for a in path[1:]]
            return tuple(path[0])
        return actions[0]
