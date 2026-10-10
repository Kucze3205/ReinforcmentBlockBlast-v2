import random

from game import Game
from policies_search import PIECE_TYPES, SearchPolicy, playable


def bits(g):
    b = 0
    for y, row in enumerate(g.board.grid):
        for x, c in enumerate(row):
            if c:
                b |= 1 << (y * 8 + x)
    return b


def punplay(b, r, n=300):
    bad = 0
    for _ in range(n):
        t = [r.choice(PIECE_TYPES[r.randrange(15)]) for _ in range(3)]
        bad += not playable(b, t)
    return bad / n


r = random.Random(1)
pol = SearchPolicy()
allp = []
deathp = []
for s in range(1, 13):
    g = Game(seed=s)
    pol.reset(s)
    hist = []
    while not g.done and g.placements < 1200:
        if g.round_placement == 0:
            hist.append(bits(g))
        g.step(pol.act(g, g.available_actions()))
    ps = [punplay(b, r, 100) for b in hist[-6:]]
    allp += [punplay(b, r, 60) for b in hist[::10]]
    if g.done:
        deathp.append(ps)
print("avg risk over play", sum(allp) / len(allp), "max", max(allp))
for d in deathp:
    print([round(x, 2) for x in d])
