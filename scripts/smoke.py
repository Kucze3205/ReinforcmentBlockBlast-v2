"""Test dymny: kilka partii bez wywrotki i czas na ruch (nie jest oceną).

Z trzecim argumentem wypisuje planszę przegranej do diagnozy.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
import policies

n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 3
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 300
show = len(sys.argv) > 3
p = policies.build(None)
for seed in range(n_games):
    g = Game(seed)
    p.reset(seed)
    t = time.time()
    n = 0
    while not g.done and n < limit:
        g.step(p.act(g, g.available_actions()))
        n += 1
    print(seed, n, g.done, round((time.time() - t) / n * 1000, 1), "ms/ruch")
    if show and g.done:
        for row in g.board.grid:
            print("".join("#" if c else "." for c in row))
        for pc in g.pieces:
            if pc:
                print(pc.name, pc.shape)
