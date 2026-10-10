"""Wiązka po tacce na bitboardach (bit = y*8+x) z ryzykiem niegrywalnej następnej tacki."""
import random

from pieces import PIECE_POOL, PIECE_TYPES

FULL = (1 << 64) - 1
COL0 = 0x0101010101010101
COL7 = COL0 << 7
ROW0 = 0xFF
ROW7 = ROW0 << 56
NOT_COL0 = FULL ^ COL0
NOT_COL7 = FULL ^ COL7

# PLACEMENTS[p] = lista (maska, x, y)
PLACEMENTS = []
for _p in PIECE_POOL:
    h, w_ = len(_p.shape), len(_p.shape[0])
    base = 0
    for dy, row in enumerate(_p.shape):
        for dx, c in enumerate(row):
            if c:
                base |= 1 << (dy * 8 + dx)
    PLACEMENTS.append([(base << (y * 8 + x), x, y)
                       for y in range(8 - h + 1) for x in range(8 - w_ + 1)])

# typy trudne: belka4, belka5, prostokąt 2x3, kwadrat3, narożnik5
HARD_TYPES = [3, 4, 6, 7, 10]


def popcount(x):
    return bin(x).count("1")


def clear(b):
    """Czyści pełne linie; zwraca (plansza, liczba linii)."""
    rows = 0
    nrows = 0
    cols = 0xFF
    for r in range(8):
        byte = (b >> (8 * r)) & 0xFF
        cols &= byte
        if byte == 0xFF:
            rows |= 0xFF << (8 * r)
            nrows += 1
    if rows or cols:
        return b & ~(rows | cols * COL0), nrows + popcount(cols)
    return b, 0


def shape_penalty(b, w):
    e = ~b & FULL
    left = ((b << 1) & NOT_COL0) | COL0
    right = ((b >> 1) & NOT_COL7) | COL7
    up = ((b << 8) & FULL) | ROW0
    down = (b >> 8) | ROW7
    iso = popcount(e & left & right & up & down)
    n3 = popcount(e & ((left & right & up) | (left & right & down)
                       | (left & up & down) | (right & up & down)))
    trans = popcount((b ^ (b >> 1)) & NOT_COL7) + popcount(b ^ (b >> 8))
    v = w[0] * popcount(b) + w[1] * iso + w[2] * n3 + w[3] * trans
    if len(w) > 4:
        rs = cs = 0
        for r in range(8):
            rs += popcount((b >> (8 * r)) & 0xFF) ** 2
            cs += popcount(b & (COL0 << r)) ** 2
        v += w[4] * rs + w[5] * cs
    if len(w) > 8:
        v += w[8] * (popcount(~b & COL0) + popcount(~b & COL7) + popcount(~b & ROW0) + popcount(~b & ROW7))
    if len(w) > 6:
        over = popcount(b) - w[7]
        if over > 0:
            v += w[6] * over * over
    return v


def _components(e):
    """Rozmiary spójnych obszarów pustych pól (e = maska pustych)."""
    sizes = []
    while e:
        seed = e & -e
        comp = seed
        while True:
            grow = comp | ((comp << 1) & NOT_COL0) | ((comp >> 1) & NOT_COL7) \
                | ((comp << 8) & FULL) | (comp >> 8)
            grow &= e
            if grow == comp:
                break
            comp = grow
        sizes.append(popcount(comp))
        e &= ~comp
    return sizes


def features(b):
    """Wektor cech planszy po komplecie klocków (do wyuczonej oceny)."""
    e = ~b & FULL
    left = ((b << 1) & NOT_COL0) | COL0
    right = ((b >> 1) & NOT_COL7) | COL7
    up = ((b << 8) & FULL) | ROW0
    down = (b >> 8) | ROW7
    iso = popcount(e & left & right & up & down)
    n3 = popcount(e & ((left & right & up) | (left & right & down)
                       | (left & up & down) | (right & up & down)))
    tr = popcount((b ^ (b >> 1)) & NOT_COL7)
    tc = popcount(b ^ (b >> 8))
    rs = cs = r6 = c6 = 0
    for r in range(8):
        n = popcount((b >> (8 * r)) & 0xFF)
        rs += n * n
        r6 += n >= 6
        n = popcount(b & (COL0 << r))
        cs += n * n
        c6 += n >= 6
    comps = _components(e)
    f = [1.0, popcount(b), iso, n3, tr, tc, rs / 8.0, cs / 8.0, r6, c6,
         len(comps), sum(1 for s in comps if s <= 3), max(comps) if comps else 0]
    for poses in PIECE_TYPES:
        t = sum(sum(1 for m, _, _ in PLACEMENTS[p] if not b & m) for p in poses) / len(poses)
        f.append(1.0 if t == 0 else 0.0)
        f.append(1.0 if t <= 2 else 0.0)
        f.append(1.0 if t <= 5 else 0.0)
        f.append(min(t, 10.0))
    return f


def playable(b, pieces):
    """Czy da się postawić wszystkie klocki (indeksy póz) w jakiejś kolejności."""
    if not pieces:
        return True
    seen = set()
    for i, p in enumerate(pieces):
        if p in seen:
            continue
        seen.add(p)
        rest = pieces[:i] + pieces[i + 1:]
        for m, _, _ in PLACEMENTS[p]:
            if not b & m:
                if playable(clear(b | m)[0], rest):
                    return True
    return False


class SearchPolicy:
    name = "search"

    def __init__(self, beam=60, final=20, samples=50, w=None, risk_w=1000.0, seed=0, lw=0.0, mob_w=None,
                 vw=None, vscale=100.0, risk_scale=1.0, fit_w=0.0, fit_cap=4.0, zero_w=0.0,
                 k2=0, n2=200, rk=0, rm=6, depth=2, qbeam=6, roll_w=300.0, shape_w=0.0):
        self.k2, self.n2 = k2, n2
        self.rk, self.rm, self.depth, self.qbeam, self.roll_w, self.shape_w = rk, rm, depth, qbeam, roll_w, shape_w
        self.fit_w, self.fit_cap, self.zero_w = fit_w, fit_cap, zero_w
        self.vw, self.vscale, self.risk_scale = vw, vscale, risk_scale
        self.mob_w = mob_w
        self.lw = lw
        self.beam, self.final, self.samples = beam, final, samples
        self.w = w or (1.0, 6.0, 2.0, 3.0)
        self.risk_w = risk_w
        self._seed = seed
        self.rng = random.Random(seed)
        # trójki trudnych typów ważone prawdopodobieństwem multizbioru (1/3/6 z 125)
        self.triples = []
        ht = HARD_TYPES
        for i in range(len(ht)):
            for j in range(i, len(ht)):
                for k in range(j, len(ht)):
                    mult = {1: 1, 2: 3, 3: 6}[len({i, j, k})]
                    self.triples.append((ht[i], ht[j], ht[k], mult / 125.0))

    def reset(self, game_seed):
        self.rng = random.Random(f"{self._seed}:{game_seed}")

    def _risk(self, b):
        dead = [not any(not b & m for m, _, _ in PLACEMENTS[p])
                for p in range(len(PIECE_POOL))]
        p_dead = sum(sum(dead[p] for p in poses) / len(poses) / 15.0
                     for poses in PIECE_TYPES)
        if p_dead >= 0.999:
            return self.risk_w * 6
        risk = self.risk_w * 2 * (1 - (1 - p_dead) ** 3)
        if self.fit_w:
            for poses in PIECE_TYPES:
                t = sum(sum(1 for m, _, _ in PLACEMENTS[p] if not b & m) for p in poses) / len(poses)
                risk -= self.fit_w * min(t, self.fit_cap)
                if t < 1.0:
                    risk += self.zero_w
        if self.mob_w:
            mw = self.mob_w
            for k, t_ in enumerate(HARD_TYPES):
                poses = PIECE_TYPES[t_]
                t = 0
                for p in poses:
                    t += sum(1 for m, _, _ in PLACEMENTS[p] if not b & m)
                risk -= mw[k] * min(t / len(poses), 8.0)
        # te same tacki dla wszystkich liści jednego ruchu (wspólne liczby losowe)
        for tray, wt in self._hard_trays:
            if any(dead[p] for p in tray) or not playable(b, tray):
                risk += self.risk_w * wt * 6
        bad = 0
        for tray in self._rand_trays:
            if any(dead[p] for p in tray) or not playable(b, tray):
                bad += 1
        return risk + self.risk_w * 2 * bad / self.samples

    def act(self, game, actions):
        rnd = self.rng
        self._hard_trays = [([rnd.choice(PIECE_TYPES[a]), rnd.choice(PIECE_TYPES[c]),
                              rnd.choice(PIECE_TYPES[d])], wt)
                            for a, c, d, wt in self.triples]
        self._rand_trays = [[rnd.choice(PIECE_TYPES[rnd.randrange(15)]) for _ in range(3)]
                            for _ in range(self.samples)]
        self._trays2 = [[rnd.choice(PIECE_TYPES[rnd.randrange(15)]) for _ in range(3)]
                        for _ in range(self.n2)] if self.k2 else []
        pieces = [p.index if p else None for p in game.pieces]
        idxs = [i for i, p in enumerate(pieces) if p is not None]
        b0 = 0
        for y, row in enumerate(game.board.grid):
            for x, c in enumerate(row):
                if c:
                    b0 |= 1 << (y * 8 + x)
        w = self.w
        level = {(b0, 0): (None, 0)}  # (plansza, użyte) -> (pierwszy ruch, linie)
        stuck = []
        for _ in idxs:
            nxt = {}
            for (b, used), (fa, ln) in level.items():
                moved = False
                for i in idxs:
                    if used >> i & 1:
                        continue
                    for m, x, y in PLACEMENTS[pieces[i]]:
                        if b & m:
                            continue
                        moved = True
                        nb, l = clear(b | m)
                        key = (nb, used | 1 << i)
                        old = nxt.get(key)
                        if old is None or ln + l > old[1]:
                            nxt[key] = (fa if fa is not None else (i, x, y), ln + l)
                if not moved and fa is not None:
                    stuck.append((shape_penalty(b, w) + 1000 - self.lw * ln, fa))
            if len(nxt) > self.beam:
                keyed = sorted(nxt.items(),
                               key=lambda kv: shape_penalty(kv[0][0], w) - self.lw * kv[1][1])
                nxt = dict(keyed[:self.beam])
            level = nxt
        scored = sorted(((shape_penalty(b, w) - self.lw * ln, b, fa)
                         for (b, used), (fa, ln) in level.items()), key=lambda t: t[0])
        if not scored or scored[0][2] is None:
            stuck.sort(key=lambda t: t[0])
            return tuple(stuck[0][1]) if stuck else actions[0]
        cands = []
        for s, b, fa in scored[:self.final]:
            cands.append((s + self._risk(b), b, fa))
        if self.rk and len(cands) > 1:
            cands.sort(key=lambda t: t[0])
            cands = cands[:self.rk]
            seqs = [[[rnd.choice(PIECE_TYPES[rnd.randrange(15)]) for _ in range(3)]
                     for _ in range(self.depth)] for _ in range(self.rm)]
            out = []
            for v, b, fa in cands:
                dead = 0.0
                shape = 0.0
                for seq in seqs:
                    bb = b
                    for k, tray in enumerate(seq):
                        bb = self._quick(bb, tray)
                        if bb is None:
                            dead += self.depth - k
                            break
                    else:
                        shape += shape_penalty(bb, w)
                out.append((v + self.roll_w * dead / self.rm + self.shape_w * shape / self.rm, fa))
            cands = [(v, None, fa) for v, fa in out]
        if self.k2 and len(cands) > 1:
            cands.sort(key=lambda t: t[0])
            extra = []
            for v, b, fa in cands[:self.k2]:
                bad = 0
                for tray in self._trays2:
                    if not playable(b, tray):
                        bad += 1
                extra.append((v + self.risk_w * 2 * bad / len(self._trays2), b, fa))
            cands = extra
        best, best_v = None, None
        for v, _, fa in cands:
            if best_v is None or v < best_v:
                best, best_v = fa, v
        return tuple(best)

    def _quick(self, b, tray):
        """Najlepsze (wg ksztaltu) ulozenie calej tacki, waska wiazka; None gdy sie nie da."""
        w = self.w
        level = {(b, 0)}
        n = len(tray)
        for _ in range(n):
            nxt = set()
            for bb, used in level:
                for i in range(n):
                    if used >> i & 1:
                        continue
                    for m, _, _ in PLACEMENTS[tray[i]]:
                        if not bb & m:
                            nxt.add((clear(bb | m)[0], used | 1 << i))
            if not nxt:
                return None
            if len(nxt) > self.qbeam:
                nxt = set(sorted(nxt, key=lambda t: shape_penalty(t[0], w))[:self.qbeam])
            level = nxt
        return min(level, key=lambda t: shape_penalty(t[0], w))[0]
