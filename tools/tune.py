"""Lokalny wskaźnik kierunku: N partii z limitem postawień, wagi/stałe z argumentów KEY=VAL.

    python tools/tune.py 500 40 trans=3 BEAM=40
Nie jest oceną.
"""
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, ".")


def run(args):
    cap, seed, over = args
    import survival
    from benchmark import play_game

    for k, v in over.items():
        if k in survival.W:
            survival.W[k] = v
        else:
            setattr(survival, k, int(v))
    return play_game(survival.SurvivalPolicy(), seed, cap)[1]


if __name__ == "__main__":
    cap, n = int(sys.argv[1]), int(sys.argv[2])
    over = {a.split("=")[0]: float(a.split("=")[1]) for a in sys.argv[3:]}
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(run, [(cap, s, over) for s in range(1000, 1000 + n)]))
    lost = sum(r < cap for r in res)
    print(over, "sr=%.0f" % (sum(res) / n), "przegranych=%d/%d" % (lost, n))
