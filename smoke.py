import sys
import time

import policies
from game import Game

cap = int(sys.argv[1])
n = int(sys.argv[2])
pol = policies.build(None)
t = time.time()
lost = tot = 0
for s in range(1, n + 1):
    g = Game(seed=s)
    pol.reset(s)
    while not g.done and g.placements < cap:
        g.step(pol.act(g, g.available_actions()))
    tot += g.placements
    lost += g.done
print("lost", lost, "/", n, "mean", tot / n, "time", round(time.time() - t, 1))
