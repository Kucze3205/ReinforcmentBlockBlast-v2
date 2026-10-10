"""Szybki test, czy polityka gra bez wywrotki: python tools/smoke.py EDGE_W [partie] [limit]."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game  # noqa: E402
import search_policy as sp  # noqa: E402

for kv in (sys.argv[1].split(",") if len(sys.argv) > 1 and "=" in sys.argv[1] else []):
    k, v = kv.split("=")
    sp.P[k] = float(v)
games = int(sys.argv[2]) if len(sys.argv) > 2 else 8
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 800
res = []
t = time.time()
for seed in range(1, games + 1):
    g = Game(seed)
    p = sp.build(None)
    p.reset(seed)
    n = 0
    while not g.done and n < limit:
        g.step(p.act(g, g.available_actions()))
        n += 1
    res.append(n)
print(sp.P, res, round(time.time() - t), "s")
