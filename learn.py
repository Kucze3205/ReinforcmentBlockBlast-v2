"""Uczenie oceny planszy: regresja na liczbie tac do przegranej (własny symulator, nie ocena)."""
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

from game import Game
from policies_search import SearchPolicy, features

CAP = 700
HORIZON = 30


def play(a):
    kw, s = a
    pol = SearchPolicy(**kw)
    g = Game(seed=s)
    pol.reset(s)
    rows = []
    while not g.done and g.placements < CAP:
        if g.round_placement == 0:
            b = 0
            for y, row in enumerate(g.board.grid):
                for x, c in enumerate(row):
                    if c:
                        b |= 1 << (y * 8 + x)
            rows.append(features(b))
        g.step(pol.act(g, g.available_actions()))
    n = len(rows)
    died = g.done
    X, y = [], []
    for i, f in enumerate(rows):
        rem = (n - i) if died else HORIZON
        X.append(f)
        y.append(min(rem, HORIZON) / HORIZON)
    return X, y, g.placements, died


if __name__ == "__main__":
    rounds = int(sys.argv[1])
    ngames = int(sys.argv[2])
    kw = {"w": (1, 6, 2, 3), "risk_w": 100.0}
    try:
        vw = json.load(open("value_weights.json"))
        kw.update(vw=vw, vscale=float(sys.argv[3]) if len(sys.argv) > 3 else 100.0)
    except FileNotFoundError:
        pass
    Xs, ys = [], []
    with Pool(4) as pool:
        for rd in range(rounds):
            t = time.time()
            res = pool.map(play, [(kw, 1000 * rd + s) for s in range(1, ngames + 1)])
            for X, y, _, _ in res:
                Xs += X
                ys += y
            X = np.array(Xs)
            Y = np.array(ys)
            A = X.T @ X + 1.0 * np.eye(X.shape[1])
            vw = np.linalg.solve(A, X.T @ Y)
            pred = X @ vw
            print(rd, "mean placements", np.mean([r[2] for r in res]), "lost", sum(r[3] for r in res),
                  "/", ngames, "samples", len(Y), "corr", round(float(np.corrcoef(pred, Y)[0, 1]), 3),
                  round(time.time() - t), flush=True)
            json.dump(vw.tolist(), open("value_weights.json", "w"))
            kw.update(vw=vw.tolist(), vscale=100.0)
