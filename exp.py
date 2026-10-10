"""Szybki eksperyment: python exp.py NAZWA=wartość ... (nadpisuje stałe survival)."""
import sys
import time

import survival
from game import Game

for kv in sys.argv[1:]:
    k, v = kv.split("=")
    setattr(survival, k, float(v) if "." in v else int(v))

CAP, N = 300, 12
pol = survival.build(None)
t = time.time()
res = []
for s in range(N):
    g = Game(seed=s)
    pol.reset(s)
    while not g.done and g.placements < CAP:
        g.step(pol.act(g, g.available_actions()))
    res.append(g.placements)
print(sys.argv[1:], res, round(sum(res) / N / CAP, 3), round(time.time() - t))
