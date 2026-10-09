"""Test dymny wag: krótkie partie, tylko wskaźnik kierunku (to nie ocena)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import beam_policy as bp  # noqa: E402
import policies  # noqa: E402
from game import Game  # noqa: E402

BASE = dict(bp.W)


def run(cfg, risk, seeds=range(100, 124), limit=400):
    bp.W.update(BASE)
    bp.W.update(cfg)
    bp.RISK_W = risk
    r = []
    for s in seeds:
        g = Game(s)
        p = policies.build(None)
        p.reset(s)
        n = 0
        while not g.done and n < limit:
            g.step(p.act(g, g.available_actions()))
            n += 1
        r.append(n)
    return sum(r) / len(r), sum(x < limit for x in r)


if __name__ == "__main__":
    for name, cfg, risk in [
        ("base", {}, 0), ("filled2", {"filled": 2}, 0), ("filled0", {"filled": 0}, 0),
        ("fit0", {"fit": 0}, 0), ("fit4", {"fit": 4}, 0), ("iso8", {"isolated": 8}, 0),
        ("trans6", {"trans": 6}, 0), ("risk", {}, 20),
    ]:
        print(name, run(cfg, risk), flush=True)
