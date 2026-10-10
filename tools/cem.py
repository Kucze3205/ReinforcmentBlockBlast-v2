"""CEM po wagach oceny (lokalny wskaźnik: średnia liczba postawień z limitem)."""
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, ".")

KEYS = ["trans", "isolated", "fill", "fit", "sq", "near", "clear"]
START = {"trans": 3.0, "isolated": 2.0, "fill": 0.5, "fit": 1.5, "sq": 0.0, "near": 0.0, "clear": 5.0}
SIGMA = {"trans": 1.5, "isolated": 1.5, "fill": 1.0, "fit": 1.0, "sq": 0.3, "near": 2.0, "clear": 10.0}


def run(args):
    cap, seed, w = args
    import survival
    from benchmark import play_game

    survival.W.update(w)
    return play_game(survival.SurvivalPolicy(), seed, cap)[1]


def score(ex, w, cap, seeds):
    return sum(ex.map(run, [(cap, s, w) for s in seeds])) / len(seeds)


if __name__ == "__main__":
    cap, n, gens, pop = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    mean, sig = dict(START), dict(SIGMA)
    rng = random.Random(1)
    best = (-1, None)
    with ProcessPoolExecutor() as ex:
        for g in range(gens):
            seeds = [rng.randrange(10**6) for _ in range(n)]
            cands = [dict(mean)] + [{k: mean[k] + rng.gauss(0, sig[k]) for k in KEYS} for _ in range(pop - 1)]
            res = sorted(((score(ex, c, cap, seeds), c) for c in cands), key=lambda t: -t[0])
            elite = [c for _, c in res[: max(2, pop // 4)]]
            mean = {k: sum(c[k] for c in elite) / len(elite) for k in KEYS}
            sig = {k: max(0.05 * SIGMA[k], 0.7 * (sum((c[k] - mean[k]) ** 2 for c in elite) / len(elite)) ** 0.5 + 0.1 * sig[k]) for k in KEYS}
            if res[0][0] > best[0]:
                best = res[0]
            print(g, "best_gen=%.0f" % res[0][0], "mean_start=%.0f" % [s for s, c in res if c is cands[0]][0],
                  json.dumps({k: round(v, 2) for k, v in mean.items()}), flush=True)
    print("BEST", best[0], json.dumps({k: round(v, 3) for k, v in best[1].items()}))
