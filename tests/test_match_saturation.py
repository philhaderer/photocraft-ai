"""Match colours: a new area that is more saturated than its surroundings is pulled back, nothing else changes.

    python tests/test_match_saturation.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import imaging  # noqa: E402


def sat(im, box=None):
    a = np.asarray(im.convert("HSV"))[..., 1].astype(float)
    return a[box[1]:box[3], box[0]:box[2]].mean() if box else a.mean()


def main():
    size = (200, 200)
    ref = Image.new("RGB", size, (130, 120, 115))                       # a dull grey-brown picture
    gen = Image.new("RGB", size, (130, 120, 115))
    gen.paste((230, 40, 30), (70, 70, 130, 130))                         # a loud red object
    mask = Image.new("L", size, 0)
    mask.paste(255, (60, 60, 140, 140))
    box = (70, 70, 130, 130)
    s0 = sat(gen, box)
    off = imaging.match_saturation(gen, ref, mask, 0.0)
    assert off is gen                                                    # strength 0: untouched
    half = imaging.match_saturation(gen, ref, mask, 0.5)
    full = imaging.match_saturation(gen, ref, mask, 1.0)
    assert sat(full, box) < sat(half, box) < s0
    assert sat(full, box) >= s0 * 0.5 - 2                                # never more than halved
    assert abs(sum(half.getpixel((10, 10))) - sum(gen.getpixel((10, 10)))) < 30      # the dull rest hardly moves (brightness stays)
    # never raised: a dull object in a colourful picture stays as it is
    vivid = Image.new("RGB", size, (220, 60, 60))
    dull = Image.new("RGB", size, (128, 120, 118))
    assert imaging.match_saturation(dull, vivid, mask, 1.0) is dull
    # no usable surroundings (the selection is the whole picture) or no selection: unchanged
    whole = Image.new("L", size, 255)
    assert imaging.match_saturation(gen, ref, whole, 1.0) is gen
    assert imaging.match_saturation(gen, ref, Image.new("L", size, 0), 1.0) is gen
    # the model's picture may come back at another size than the crop it was given
    small = gen.resize((100, 100))
    assert imaging.match_saturation(small, ref, mask, 1.0).size == (100, 100)
    print("ALL OK (match saturation)")


if __name__ == "__main__":
    main()
