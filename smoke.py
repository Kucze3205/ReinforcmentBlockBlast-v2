import sys
import time

from game import Game
from survival import build

cap = int(sys.argv[1])
n = int(sys.argv[2])
pol = build(None)
t = time.time()
res = []
for s in range(n):
    g = Game(seed=s)
    pol.reset(s)
    while not g.done and g.placements < cap:
        g.step(pol.act(g, g.available_actions()))
    res.append(g.placements)
print(res, sum(res) / n / cap, time.time() - t)
