import sys, time

sys.path.insert(0, ".")
import policies
from game import Game

pol = policies.build(None)
for seed in range(int(sys.argv[1])):
    g = Game(seed)
    pol.reset(seed)
    n = 0
    t = time.time()
    while not g.done and n < int(sys.argv[2]):
        g.step(pol.act(g, g.available_actions()))
        n += 1
    print(seed, n, round(time.time() - t, 1), flush=True)
