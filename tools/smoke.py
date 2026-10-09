"""Test dymny: kilka krótkich partii policies.build (nie jest oceną)."""
import sys
import time

sys.path.insert(0, ".")
import policies
from benchmark import play_game

cap = int(sys.argv[1]) if len(sys.argv) > 1 else 300
n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
p = policies.build(None)
t = time.time()
for s in range(1, n + 1):
    print(s, play_game(p, s, cap), round(time.time() - t, 1), flush=True)
