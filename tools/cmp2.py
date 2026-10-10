import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import smoke_w as sw  # noqa: E402

for d in [0, 20, 40]:
    t = time.time()
    print(d, sw.run({"dead": d}, 25, seeds=range(200, 248), limit=500), round(time.time() - t), flush=True)
