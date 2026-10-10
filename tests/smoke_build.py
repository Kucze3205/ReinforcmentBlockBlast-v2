"""Dym: policies.build gra kilka krótkich partii bez wywrotki (to nie jest pomiar wyniku)."""
import time

import policies
from game import Game

if __name__ == "__main__":
    pol = policies.build(None)
    for seed in range(1, 5):
        g = Game(seed=seed)
        pol.reset(seed)
        t = time.time()
        while not g.done and g.placements < 300:
            g.step(pol.act(g, g.available_actions()))
        ms = (time.time() - t) / max(g.placements, 1) * 1000
        print(seed, g.placements, g.done, round(ms, 1), "ms/ruch")
