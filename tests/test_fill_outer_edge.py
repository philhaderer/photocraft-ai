"""Fill with an instruction editor (Qwen, Fibo), layer mask soft: the fill is fully opaque over the selection and Edge
feather around it, then fades out smoothly to 0 at the crop's sides inside the picture (Fill mask test round 30.10.,
option A); Remove keeps its feather across the edge.

    python tests/test_fill_outer_edge.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import imaging, workflows  # noqa: E402
from pccomfy.bridge import Request, soft_layer_mask  # noqa: E402

W, H = 1000, 800
SEL = (300, 250, 600, 550)      # 300 x 300: 10 % = 30 px


def sel_mask(ellipse=False):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    (d.ellipse if ellipse else d.rectangle)((SEL[0], SEL[1], SEL[2] - 1, SEL[3] - 1), fill=255)
    return m


def layer_mask(mask, wf="qwen-image-21-edit.json", pct=10.0, remove=False, context=0.4):
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / wf), layer_mask="soft", feather_pct=pct, remove=remove)
    bbox = imaging.mask_bbox(mask)
    region = imaging.grow_box(bbox, mask.size, context)
    full = np.zeros((H, W), np.uint8)
    full[region.y:region.y + region.h, region.x:region.x + region.w] = np.asarray(
        soft_layer_mask(req, workflows.resolve(req.workflow), mask, region, bbox))
    return full


def main():
    sel = np.asarray(sel_mask()) > 127
    for wf in ("qwen-image-21-edit.json", "fibo2-edit.json"):
        m = layer_mask(sel_mask(), wf)
        assert m[sel].min() == 255, "the fill must be fully opaque inside the selection"
        row = m[400]                        # a line through the middle: left edge at x = 300, the crop starts at x = 180
        assert row[300 - 28] == 255 and row[300 - 40] < 250, row[255:305]      # opaque over Edge feather (10 % = 30 px)
        assert row[180] <= 1 and 0 < row[200] < row[240] < row[260] < 255, row[175:305]   # then fading out to the crop
        assert (row[180:300].astype(int)[1:] >= row[180:300].astype(int)[:-1]).all()     # never rising outwards
        assert abs(int(m[400, 719 - 50]) - int(row[180 + 50])) <= 2      # the same on the right side (the crop ends at 719)
        assert m[129].max() == 0 and m[670].max() == 0                   # nothing outside the crop
    # 0 %: opaque exactly over the selection, the fade starts at its edge
    m0 = layer_mask(sel_mask(), pct=0.0)
    assert m0[sel].min() == 255 and m0[400, 290] < 255
    # a wider feather, a wider opaque band
    assert layer_mask(sel_mask(), pct=20.0)[400, 300 - 50] == 255 > layer_mask(sel_mask(), pct=10.0)[400, 300 - 50]
    # the mask reaches 0 at the end of the redrawn crop even with little room (its straight edge would show)
    m = layer_mask(sel_mask(), pct=50.0, context=0.05)
    bbox = imaging.mask_bbox(sel_mask())
    region = imaging.grow_box(bbox, (W, H), 0.05)
    assert m[400, region.x] <= 1 and m[sel].min() == 255, m[400, region.x]
    # Remove keeps the feather across the selection's edge (unchanged)
    r = layer_mask(sel_mask(), remove=True)
    assert r[sel].min() < 255 and r[400, 299] < 255
    # a selection that is already soft (feathered in PhotoCraft) is used as it is
    soft = sel_mask().filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(8))
    bbox = imaging.mask_bbox(soft)
    region = imaging.grow_box(bbox, (W, H), 0.4)
    assert np.array_equal(layer_mask(soft)[region.y:region.y + region.h, region.x:region.x + region.w],
                          np.asarray(soft.crop(region.pil())))
    print("ok")


if __name__ == "__main__":
    main()
