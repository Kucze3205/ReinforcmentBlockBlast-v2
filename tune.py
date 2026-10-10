import json
import sys
import time
from multiprocessing import Pool

from game import Game
from policies_search import SearchPolicy


def run(a):
    kw, s, cap = a
    pol = SearchPolicy(**kw)
    g = Game(seed=s)
    pol.reset(s)
    while not g.done and g.placements < cap:
        g.step(pol.act(g, g.available_actions()))
    return g.placements


if __name__ == "__main__":
    cap = int(sys.argv[1])
    n = int(sys.argv[2])
    for kw in map(json.loads, sys.argv[3:]):
        t = time.time()
        with Pool(4) as p:
            r = p.map(run, [(kw, s, cap) for s in range(1, n + 1)])
        print(kw, "lost", sum(x < cap for x in r), "/", n, "mean", sum(r) / n, round(time.time() - t))
