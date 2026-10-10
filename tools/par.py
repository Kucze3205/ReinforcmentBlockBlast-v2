"""Wskaźnik lokalny (nie ocena): równoległe partie. python tools/par.py cap partie [KLUCZ=wart,...]"""
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, ".")
import policies
import survival
from benchmark import play_game

for kv in (sys.argv[3].split(",") if len(sys.argv) > 3 else []):
    k, v = kv.split("=")
    if k in ("BEAM", "FINAL", "SAMPLES"):
        setattr(survival, k, int(v))
    else:
        survival.W[k] = float(v)
CAP = int(sys.argv[1])


def run(s):
    return play_game(policies.build(None), s, CAP)[1:]


if __name__ == "__main__":
    n = int(sys.argv[2])
    t = time.time()
    with Pool() as pool:
        r = pool.map(run, range(100, 100 + n), chunksize=1)
    print("sr", sum(x for x, _ in r) / n, "przegr", sum(1 for x, _ in r if x < CAP), "/", n, "t", round(time.time() - t))
