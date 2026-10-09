"""Test dymny: czy polityka gra bez wywrotki. Użycie: python tools/smoke.py [limit] [partie]."""
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, '.')
import policies
from game import Game

CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 500


def run(seed):
    p = policies.build(None)
    g = Game(seed=seed)
    p.reset(seed)
    while not g.done and g.placements < CAP:
        a = g.available_actions()
        if not a:
            break
        g.step(p.act(g, a))
    return g.placements, g.done


if __name__ == "__main__":
    t = time.time()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    with Pool(4) as pool:
        r = pool.map(run, range(1000, 1000 + n))
    print(sum(x for x, _ in r) / n, sum(d for _, d in r), time.time() - t)
