import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
import policies


def test_search_policy_plays_legal_moves():
    p = policies.build(None)
    g = Game(1)
    p.reset(1)
    while not g.done and g.placements < 60:
        _, _, _, info = g.step(p.act(g, g.available_actions()))
        assert info != "wrong_placement"
