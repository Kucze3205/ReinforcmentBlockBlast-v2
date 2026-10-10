import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import beam_policy as bp  # noqa: E402
import smoke_w as sw  # noqa: E402

for beam, leaves, risk in [(40, 30, 25), (100, 30, 25), (100, 30, 60), (100, 60, 25)]:
    bp.BEAM = beam
    bp.FIT_LEAVES = leaves
    t = time.time()
    print(beam, leaves, risk, sw.run({}, risk, seeds=range(200, 248), limit=500), round(time.time() - t), flush=True)
