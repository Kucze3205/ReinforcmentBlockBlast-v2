import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import beam_policy as bp  # noqa: E402
import smoke_w as sw  # noqa: E402

for hw in [0, 400]:
    bp.HARD_W = hw
    t = time.time()
    print(hw, sw.run({}, 25, seeds=range(200, 248), limit=500), round(time.time() - t), flush=True)
