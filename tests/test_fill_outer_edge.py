"""Fill with an instruction editor (Qwen, Fibo), layer mask soft: the fill is fully opaque over the selection, then fades out to the redrawn crop's sides (a shadow below the selection stays); Remove keeps its
feather across the edge.

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
    bbox = imaging.mask_bbox(sel_mask())
    region = imaging.grow_box(bbox, (W, H), 0.4)            # 120 px room: x 180..719
    for wf in ("qwen-image-21-edit.json", "fibo2-edit.json"):
        m = layer_mask(sel_mask(), wf)
        assert m[sel].min() == 255, "the fill must be fully opaque inside the selection"
        row = m[400]                        # a line through the middle: left edge at x = 300
        # opaque up to the selection, then a fade that ends exactly at the crop's side
        assert row[299] == 255 and row[280] > 200 and 60 < row[240] < 200 and row[region.x] == 0 and row[region.x - 1] == 0, row[175:305]
        assert abs(int(m[400, 599 + 30]) - int(row[300 - 30])) <= 2      # the same on the right side
        assert m[640, 450] > 0 and m[region.y + region.h - 1, 450] == 0   # below the selection: a shadow there stays
    # the edge feather is not used for Fill (its slider is hidden there, user 28.10.)
    assert np.array_equal(layer_mask(sel_mask(), pct=0.0), layer_mask(sel_mask(), pct=20.0))
    # a small Context: still 0 at the crop's side (its straight edge would show)
    m = layer_mask(sel_mask(), pct=50.0, context=0.05)
    region = imaging.grow_box(bbox, (W, H), 0.05)
    assert m[400, region.x] == 0, m[400, region.x]
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
