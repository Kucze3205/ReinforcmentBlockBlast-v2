"""Plansze przegranych (diagnostyka, nie ocena)."""
import sys

sys.path.insert(0, ".")
import policies
from game import Game

p = policies.build(None)
for s in range(1000, 1024):
    g = Game(seed=s)
    p.reset(s)
    while not g.done and g.placements < 500:
        a = g.available_actions()
        if not a:
            break
        g.step(p.act(g, a))
    if g.done:
        print(s, g.placements)
        for r in g.board.grid:
            print("".join("#" if c else "." for c in r))
        print([pc.shape if pc else None for pc in g.pieces])
