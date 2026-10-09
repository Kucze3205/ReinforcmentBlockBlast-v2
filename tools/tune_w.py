"""Szybki test dymny wag _eval: python tools/tune_w.py "[1.5,2,1]" ... (48 partii, limit 500 postawień)."""
import sys
sys.path.insert(0, '.')
from multiprocessing import Pool

import search_policy as sp
from game import Game


def run(a):
    w, seed = a
    sp.W[:] = w
    sp._next_tray.cache_clear()
    p = sp.SearchPolicy()
    g = Game(seed)
    while not g.done and g.placements < 500:
        g.step(p.act(g, g.available_actions()))
    return g.placements


if __name__ == "__main__":
    with Pool() as P:
        for w in map(eval, sys.argv[1:]):
            r = P.map(run, [(w, s) for s in range(1000, 1048)])
            print(w, sum(r) / len(r), sum(x < 500 for x in r), flush=True)
