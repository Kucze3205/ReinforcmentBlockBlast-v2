"""Test dymny polityki: kilka krótkich partii, czas na ruch. Nie jest pomiarem wyniku.

    python smoke.py CAP N [NAZWA=WARTOŚĆ ...]   # nadpisuje stałe modułu survival
"""
import sys
import time

import policies
import survival
from game import Game

cap = int(sys.argv[1])
n = int(sys.argv[2])
for kv in sys.argv[3:]:
    k, v = kv.split("=")
    setattr(survival, k, float(v) if "." in v else int(v))
pol = policies.build(None)
t0 = time.time()
total = 0
res = []
for s in range(n):
    g = Game(seed=s)
    pol.reset(s)
    k = 0
    while not g.done and k < cap:
        acts = g.available_actions()
        if not acts:
            break
        g.step(pol.act(g, acts))
        k += 1
    total += k
    res.append(k)
print(res, round((time.time() - t0) / max(total, 1) * 1000, 2), "ms/ruch")
