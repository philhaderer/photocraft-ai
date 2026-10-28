"""Fill's soft edge outside the selection: an edge and a corner fade alike (no display needed).

Live test 28.10.: with a rectangular selection only the straight edges were soft, the corners stayed hard (the
blur of a corner is a quarter, not a half, so twice the blur started at 0.5 there and fell off fast).

    python tests/test_outer_feather.py
"""
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402
from pccomfy import imaging  # noqa: E402


def main():
    m = Image.new("L", (400, 300), 0)
    m.paste(255, (100, 100, 300, 200))          # selection x 100..299, y 100..199
    out = imaging.outer_feather(m, 20)
    px = out.load()
    # inside fully opaque, the edge starts opaque and fades to ~0 at the radius
    assert px[200, 150] == 255 and px[100, 100] == 255 and px[299, 199] == 255
    edge = [px[300 + d, 150] for d in (0, 10, 20, 30)]       # right of the right edge
    assert edge[0] >= 240 and 60 < edge[1] < 90 and edge[2] < 20 and edge[3] <= 1, edge
    # the corner: the same fade along the diagonal at the same distance (round, not hard)
    for d in (5, 10, 15, 20):
        k = round(d / math.sqrt(2))
        corner = px[299 + k, 199 + k]
        straight = px[299 + round(math.hypot(k, k)), 150]
        assert abs(corner - straight) <= 12, (d, corner, straight)
    # symmetric: all four corners alike
    assert px[299 + 7, 199 + 7] == px[100 - 7, 100 - 7] == px[299 + 7, 100 - 7] == px[100 - 7, 199 + 7]
    # nothing at the far corner of the picture, 0 radius and a soft mask stay as they are
    assert px[0, 0] == 0 and px[399, 299] == 0
    assert imaging.outer_feather(m, 0).tobytes() == m.tobytes()
    soft = imaging.auto_feather(m, 20)
    assert imaging.outer_feather(soft, 20).tobytes() == soft.tobytes()
    # fast enough for a large selection
    big = Image.new("L", (1600, 1200), 0)
    big.paste(255, (200, 200, 1400, 1000))
    t0 = time.time()
    imaging.outer_feather(big, 80)
    assert time.time() - t0 < 5.0, time.time() - t0
    print("ALL OK (outer feather)")


if __name__ == "__main__":
    main()
