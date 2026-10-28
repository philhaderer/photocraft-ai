"""Fill with an instruction editor (Qwen, Fibo), layer mask soft: the fill is fully opaque up to the selection's edge, the
soft edge lies OUTSIDE the selection and is as wide as the edge feather says; Remove keeps its feather across the edge.

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
        row = m[400]                        # a line through the middle: left edge at x = 300
        assert row[299] > 230 and 60 < row[300 - 15] < 200 and row[300 - 30] < 20 and row[300 - 40] == 0, row[255:305]
        assert m[400, 600 + 15] == row[300 - 16]          # the same on the right side
    # 0 % = hard edge: exactly the selection
    assert np.array_equal(layer_mask(sel_mask(), pct=0.0) > 0, sel)
    # a wider feather, a wider edge
    assert layer_mask(sel_mask(), pct=20.0)[400, 300 - 30] > layer_mask(sel_mask(), pct=10.0)[400, 300 - 30]
    # the edge never reaches the end of the redrawn crop (its straight edge would show): context 0.05 = 32 px room
    m = layer_mask(sel_mask(), pct=50.0, context=0.05)
    bbox = imaging.mask_bbox(sel_mask())
    region = imaging.grow_box(bbox, (W, H), 0.05)
    assert m[400, region.x] < 15, m[400, region.x]
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
