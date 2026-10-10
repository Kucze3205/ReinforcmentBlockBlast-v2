"""Kontrola działania (bez wywrotki): python smoke.py <partie> <maks_ruchów>."""
import sys
import time

import policies
from game import Game

policy = policies.build(None)
for seed in range(int(sys.argv[1])):
    g = Game(seed)
    policy.reset(seed)
    n = 0
    t = time.time()
    while not g.done and n < int(sys.argv[2]):
        actions = g.available_actions()
        if not actions:
            break
        g.step(policy.act(g, actions))
        n += 1
    print(seed, n, g.score, round(time.time() - t, 1), flush=True)
