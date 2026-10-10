"""Strojenie wag przeszukiwaniem losowym wokół najlepszego punktu (tylko do dostrajania, nie ocena)."""
import json
import random
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, ".")
import policies_search as ps
from game import Game

DEFAULT = dict(line=0.0, fill=6.0, iso=15.0, pocket=70.0, trans=22.4, clear=10.0,
               risk_w=750.0, mob_w=0.7)
SEEDS, CAP = 16, 500


def run(args):
    cfg, seed = args
    ps.W.update({k: v for k, v in cfg.items() if k in ps.W})
    pol = ps.SearchPolicy(beam=30, final=8, risk_w=cfg["risk_w"], mob_w=cfg["mob_w"])
    g = Game(seed + 1000)
    pol.reset(seed)
    n = 0
    while not g.done and n < CAP:
        g.step(pol.act(g, g.available_actions()))
        n += 1
    return n


def score(pool, cfg, offset):
    res = pool.map(run, [(cfg, offset + s) for s in range(SEEDS)])
    return sum(res) / len(res)


if __name__ == "__main__":
    rng = random.Random(7)
    best = dict(DEFAULT)
    with Pool(4) as pool:
        t = time.time()
        bs = score(pool, best, 0)
        print("start", round(bs, 1), round(time.time() - t), flush=True)
        for it in range(int(sys.argv[1])):
            cand = dict(best)
            for k in rng.sample(list(cand), 2):
                if k == "line":
                    continue
                cand[k] = max(0.0, cand[k] * rng.choice([0.5, 0.7, 1.4, 2.0]))
            s = score(pool, cand, 0)
            print(it, round(s, 1), {k: round(v, 2) for k, v in cand.items()}, flush=True)
            if s > bs:
                best, bs = cand, s
                print("BEST", round(bs, 1), json.dumps(best), flush=True)
