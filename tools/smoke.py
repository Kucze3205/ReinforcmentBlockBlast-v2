"""Test dymny: kilka partii z limitem postawień (nie jest oceną)."""
import sys
import time

sys.path.insert(0, ".")
import policies
from game import Game

p = policies.build(None)
t = time.time()
res = []
for s in range(1, 13):
    g = Game(seed=s)
    p.reset(s)
    while not g.done and g.placements < 500:
        a = g.available_actions()
        if not a:
            break
        g.step(p.act(g, a))
    res.append(g.placements)
print(res, time.time() - t)
