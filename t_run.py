import sys, time
from game import Game
import policies

p = policies.build(None)
for s in range(int(sys.argv[1])):
    g = Game(s)
    p.reset(s)
    t = time.time()
    while not g.done and g.placements < int(sys.argv[2]):
        a = g.available_actions()
        if not a:
            break
        g.step(p.act(g, a))
    print(s, g.placements, g.score, round(time.time() - t, 1), flush=True)
