"""Fill's layer mask outside the selection (imaging.crop_fade): round at the corners, 0 at the crop's sides inside the
picture, no fade on a side at the canvas edge (no display needed).

Live test 28.10.: with a rectangular selection only the straight edges were soft, the corners stayed hard; later the
narrow soft edge cut off the object's edge and its shadow, so the fade now runs out to the crop's sides.

    python tests/test_outer_feather.py
"""
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageFilter  # noqa: E402
from pccomfy import imaging  # noqa: E402

ALL = (True, True, True, True)


def main():
    m = Image.new("L", (400, 300), 0)
    m.paste(255, (100, 100, 300, 200))          # selection x 100..299, y 100..199; 100 px room on every side
    out = imaging.crop_fade(m, 0, ALL)
    px = out.load()
    # inside fully opaque, outside it falls to 0 at the crop's sides
    assert px[200, 150] == 255 and px[100, 100] == 255 and px[299, 199] == 255
    edge = [px[300 + d, 150] for d in (0, 25, 50, 75, 99)]       # right of the right edge
    assert edge[0] >= 245 and 150 < edge[1] < 240 and 100 < edge[2] < 155 and edge[3] < 60 and edge[4] == 0, edge
    assert px[0, 150] == 0 and px[200, 0] == 0 and px[0, 0] == 0 and px[399, 299] == 0
    # the corner: round, not hard (no edge along the diagonal)
    for d in (10, 20, 30):
        k = round(d / math.sqrt(2))
        assert px[299 + k, 199 + k] > px[299 + d, 150] - 80, (d, px[299 + k, 199 + k], px[299 + d, 150])
    assert px[299 + 7, 199 + 7] == px[100 - 7, 100 - 7] == px[299 + 7, 100 - 7] == px[100 - 7, 199 + 7]
    # the edge feather keeps a band fully opaque, a wider one keeps more
    wide = imaging.crop_fade(m, 40, ALL).load()
    assert wide[330, 150] == 255 and wide[340, 150] >= 250 and wide[399, 150] == 0
    assert imaging.crop_fade(m, 200, ALL).load()[375, 150] < 255     # capped: at least 30 % of the room fades
    # a side on the canvas edge does not fade: the left side here
    left = imaging.crop_fade(m, 0, (False, True, True, True)).load()
    assert left[0, 150] > 100 and left[399, 150] == 0 and left[0, 150] > out.load()[0, 150]
    # the crop is the whole picture: no fade at all
    assert imaging.crop_fade(m, 0, (False,) * 4).getextrema() == (255, 255)
    # a soft mask (feathered in PhotoCraft) stays as it is
    soft = m.filter(ImageFilter.GaussianBlur(10))
    assert imaging.crop_fade(soft, 20, ALL).tobytes() == soft.tobytes()
    # fast enough for a large crop
    big = Image.new("L", (2400, 1800), 0)
    big.paste(255, (600, 500, 1800, 1300))
    t0 = time.time()
    imaging.crop_fade(big, 80, ALL)
    assert time.time() - t0 < 5.0, time.time() - t0
    print("ALL OK (crop fade)")


if __name__ == "__main__":
    main()
