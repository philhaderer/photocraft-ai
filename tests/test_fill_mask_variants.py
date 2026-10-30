"""Fill mask test round, stage 1 (no GPU; user 30.10.): every layer-mask variant of pccomfy/fillmask.py at every position
(middle, touching each canvas edge, in two corners, a few px from an edge), as rectangle and as hard lasso, with several
Edge feather and Context values, against fixed rules:

    1  the selection is fully opaque, also where it meets the canvas edge
    2  no fade towards the canvas edge (the fault of 28.10.: the fill went soft at a picture edge)
    3  a side of the crop inside the picture: crop_fade 0, narrow/wide at most a trace (printed), density5 >= 95 %
    4  crop_fade is exactly what the plugin does since 30.10. (bridge.soft_layer_mask); corners fade like edges
       (narrow, wide)

    python tests/test_fill_mask_variants.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import fillmask, imaging  # noqa: E402
from pccomfy.bridge import Request, soft_layer_mask  # noqa: E402

W, H = 800, 600
SW, SH = 180, 150                     # selection size
POSITIONS = {"middle": ((W - SW) // 2, (H - SH) // 2), "left": (0, (H - SH) // 2), "top": ((W - SW) // 2, 0),
             "right": (W - SW, (H - SH) // 2), "bottom": ((W - SW) // 2, H - SH), "top-left": (0, 0),
             "bottom-right": (W - SW, H - SH), "near-left": (3, (H - SH) // 2)}
FIBO = str(ROOT / "workflows" / "fibo2-edit.json")


def selection(pos: str, shape: str) -> Image.Image:
    x, y = POSITIONS[pos]
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    if shape == "rect":
        d.rectangle((x, y, x + SW - 1, y + SH - 1), fill=255)
    else:            # a hard lasso: an uneven blob filling the box (no anti-aliasing, as PhotoCraft without smoothing)
        cx, cy = x + SW / 2, y + SH / 2
        pts = [(cx + SW / 2 * (0.85 + 0.15 * np.sin(3 * t)) * np.cos(t), cy + SH / 2 * (0.85 + 0.15 * np.cos(2 * t)) * np.sin(t))
               for t in np.linspace(0, 2 * np.pi, 48, endpoint=False)]
        d.polygon([(min(W - 1, max(0, px)), min(H - 1, max(0, py))) for px, py in pts], fill=255)
    return m


def beyond_edge(v, mask, region, bbox, pct, inner, pad=120):
    """The same variant as if the picture went on past its edges: the crop padded with empty canvas on every side that
    lies on the canvas edge (the sides inside the picture stay), the same widths, cut back to the crop."""
    sel = mask.convert("L").crop(region.pil())
    l, t, r, b = (0 if on else pad for on in inner)
    big = Image.new("L", (sel.width + l + r, sel.height + t + b), 0)
    big.paste(sel, (l, t))
    radius = imaging.feather_radius(bbox.w, bbox.h, pct)
    if v == "crop_fade":
        m = fillmask.crop_fade(big, radius, inner)
    else:
        m = imaging.outer_feather(big, fillmask.room(mask.size, region, bbox, round(radius * (fillmask.WIDE if v == "wide" else 1))))
    return m.crop((l, t, l + sel.width, t + sel.height))


def check(pos, shape, pct, ctx, report):
    mask = selection(pos, shape)
    bbox = imaging.mask_bbox(mask)
    region = imaging.grow_box(bbox, (W, H), ctx)
    sel = np.asarray(mask.crop(region.pil())) > 127
    inner = (region.x > 0, region.y > 0, region.x + region.w < W, region.y + region.h < H)
    for v in fillmask.VARIANTS:
        m, dens = fillmask.layer_mask(v, mask, region, bbox, pct)
        a = np.asarray(fillmask.effective(m, dens), dtype=np.int16)
        case = f"{v} {pos} {shape} feather {pct} % context {ctx}"
        assert a.shape == sel.shape, case
        assert (a[sel] == 255).all(), f"rule 1: {case}"                                   # the selection is opaque
        ref = np.asarray(fillmask.effective(beyond_edge(v, mask, region, bbox, pct, inner), dens), dtype=np.int16)
        gap = int(np.abs(a - ref).max())                                                  # rule 2: no fade to the canvas
        assert gap <= 2, f"rule 2: {case}: {gap} levels off where the picture ends"
        sides = ([a[:, 0]] if inner[0] else []) + ([a[0, :]] if inner[1] else []) + \
                ([a[:, -1]] if inner[2] else []) + ([a[-1, :]] if inner[3] else [])
        top = max((int(s.max()) for s in sides), default=0)
        if v == "crop_fade":
            assert top <= 1, f"rule 3: {case}: {top} at the crop's side"
        elif v == "density5":
            assert a.min() >= 242, f"rule 3: {case}"
        else:
            assert top <= 16, f"rule 3: {case}: {top} at the crop's side"
            report[v] = max(report.get(v, 0), top)
        if v == "crop_fade":                                                              # rule 4: the plugin's own mask
            today = soft_layer_mask(Request(mode="inpaint", workflow=FIBO, feather_pct=pct), [FIBO], mask, region, bbox)
            assert np.array_equal(np.asarray(today), np.asarray(m)), f"rule 4: {case}"


def corners_round():
    """Rule 4b: beyond a corner of a rectangle the mask fades over the same distance as beside an edge."""
    mask = selection("middle", "rect")
    bbox = imaging.mask_bbox(mask)
    region = imaging.grow_box(bbox, (W, H), 0.8)
    for v in ("narrow", "wide"):
        m, _ = fillmask.layer_mask(v, mask, region, bbox, 10.0)
        a = np.asarray(m, dtype=np.int16)
        x1, y1 = bbox.x + bbox.w - 1 - region.x, bbox.y + bbox.h - 1 - region.y     # the bottom-right corner in the crop
        for k in (4, 8, 12):
            side = a[y1 - 20, x1 + k]
            diag = a[y1 + round(k / 2 ** 0.5), x1 + round(k / 2 ** 0.5)]
            assert abs(int(side) - int(diag)) <= 14, (v, k, side, diag)


def main():
    report, n = {}, 0
    for pos in POSITIONS:
        for shape in ("rect", "lasso"):
            for pct in (4.0, 10.0, 20.0):
                for ctx in (0.2, 0.4, 0.8):
                    check(pos, shape, pct, ctx, report)
                    n += 1
    corners_round()
    print(f"test_fill_mask_variants: ok ({n} cases x {len(fillmask.VARIANTS)} variants; most at a crop side: "
          + ", ".join(f"{v} {t}" for v, t in sorted(report.items())) + ")")


if __name__ == "__main__":
    main()
