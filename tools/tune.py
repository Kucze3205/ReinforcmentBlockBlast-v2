"""Strojenie wag oceny liści losowym lokalnym szukaniem: python tools/tune.py [rundy] [partie] [limit].

Seedy strojenia (1000+) są rozłączne z seedami smoke.py. To lokalna heurystyka do wyboru wag,
nie pomiar wyniku — ten liczy ocena.
"""
import copy
import os
import random
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game  # noqa: E402
import search_policy as sp  # noqa: E402

GAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 16
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 600
KEYS = ["occ", "iso", "edge", "wall", "line", "risk", "fit", "dead"]


def play(args):
    params, seed = args
    sp.P.update(params)
    g = Game(seed)
    p = sp.build(None)
    p.reset(seed)
    n = 0
    while not g.done and n < LIMIT:
        g.step(p.act(g, g.available_actions()))
        n += 1
    return n


def score(pool, params):
    return sum(pool.map(play, [(params, 1000 + s) for s in range(GAMES)])) / GAMES


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    rng = random.Random(0)
    with Pool(4) as pool:
        best = copy.deepcopy(sp.P)
        best_s = score(pool, best)
        print("start", best_s, flush=True)
        for r in range(rounds):
            cand = copy.deepcopy(best)
            for k in rng.sample(KEYS, 2):
                cand[k] = max(0.0, cand[k] * rng.choice([0.5, 0.7, 1.4, 2.0]) + rng.choice([0, 0.5]))
            s = score(pool, cand)
            print(r, round(s, 1), {k: round(cand[k], 2) for k in KEYS}, flush=True)
            if s > best_s:
                best, best_s = cand, s
                print("BEST", best_s, {k: round(best[k], 2) for k in KEYS}, flush=True)
