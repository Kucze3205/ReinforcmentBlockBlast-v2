"""CEM na wagach SearchPolicy (własny symulator, to nie ocena)."""
import json
import random
import sys
import time
from multiprocessing import Pool

from game import Game
from policies_search import SearchPolicy

CAP = 400
NG = 32
# w0..w5, mob x5, risk_w
MEAN = [1, 6, 2, 3, 0, 0, 0, 0, 0, 0, 0, 100]
SD = [1, 4, 2, 2, 0.5, 0.5, 5, 5, 5, 5, 5, 60]


def mk(th):
    return SearchPolicy(w=tuple(th[:6]), mob_w=th[6:11], risk_w=max(th[11], 0.0), beam=40, final=8, samples=8)


def run(a):
    th, s = a
    pol = mk(th)
    g = Game(seed=s)
    pol.reset(s)
    while not g.done and g.placements < CAP:
        g.step(pol.act(g, g.available_actions()))
    return g.placements


if __name__ == "__main__":
    rng = random.Random(1)
    mean, sd = MEAN[:], SD[:]
    P = 14
    with Pool(4) as pool:
        for gen in range(int(sys.argv[1])):
            t = time.time()
            seeds = [rng.randrange(10**6) for _ in range(NG)]
            cands = [mean] + [[rng.gauss(m, s) for m, s in zip(mean, sd)] for _ in range(P - 1)]
            res = []
            for th in cands:
                r = pool.map(run, [(th, s) for s in seeds])
                res.append((sum(r) / NG, th))
            res.sort(key=lambda x: -x[0])
            elite = [th for _, th in res[:4]]
            mean = [sum(e[i] for e in elite) / 4 for i in range(len(mean))]
            sd = [max(0.7 * sd[i] + 0.3 * (sum((e[i] - mean[i]) ** 2 for e in elite) / 4) ** 0.5, 0.05) for i in range(len(sd))]
            print(gen, round(res[0][0], 1), "mean-of-mean", [round(x, 2) for x in mean], round(time.time() - t), flush=True)
            json.dump(mean, open("cem_mean.json", "w"))
