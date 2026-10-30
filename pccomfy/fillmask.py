"""Layer-mask variants for Fill with an instruction editor (Qwen, Fibo), from the Fill mask test round (PLAN, "Fill-Maske
neu"; user 30.10.). The winner, crop_fade, is the plugin's Fill mask (bridge.soft_layer_mask, user 30.10.: option A);
the others stay for the live test round (tests/live_fill_mask.py).

Qwen and Fibo never see the mask: they redraw the whole crop around the selection, and PhotoCraft blends the result in
through the layer mask. So one generation can be shown with every variant; the masks are built here, the size of the
crop (`region`), from the selection mask of the whole picture.

    narrow     the mask before 30.10.: opaque over the selection, a soft edge outside it, as wide as Edge feather (stops
               before the crop ends)
    density5   the same mask at 5 % density (the Fill start value before 30.10.): the whole crop shows at 95 % or more
    crop_fade  opaque over the selection and Edge feather around it, then a smooth fade reaching 0 at the crop's sides
               inside the picture (the attempt of 28.10.); no fade where the crop meets the canvas edge
               (bridge.soft_layer_mask itself since 30.10.)
    wide       as narrow, three times as wide (still stopping before the crop ends)

Rules every variant keeps (tests/test_fill_mask_variants.py): the selection is fully opaque, also where it meets the
canvas edge; a side of the crop inside the picture is 0 (except density5, which is the point of it); the fade only falls
with the distance to the selection, so a corner fades like an edge."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

from . import imaging

VARIANTS = {"narrow": "heute: schmaler Rand", "density5": "heute: Dichte 5 %",
            "crop_fade": "bis zum Ausschnittrand", "wide": "breiter Rand außen (3×)"}
WIDE = 3.0


def room(size: tuple[int, int], region: imaging.Box, bbox: imaging.Box, radius: int) -> int:
    """How far the soft edge may reach: the radius, but not past a side of the crop that lies inside the picture."""
    W, H = size
    gaps = [bbox.x - region.x if region.x > 0 else radius, bbox.y - region.y if region.y > 0 else radius,
            region.x + region.w - (bbox.x + bbox.w) if region.x + region.w < W else radius,
            region.y + region.h - (bbox.y + bbox.h) if region.y + region.h < H else radius]
    return max(0, min([radius] + gaps))


def crop_fade(mask: Image.Image, radius: int, inner: tuple[bool, bool, bool, bool]) -> Image.Image:
    """Opaque over the selection and `radius` px around it, then a smooth fade that reaches 0 exactly at the crop's sides
    inside the picture (`inner` = left, top, right, bottom; a side on the canvas edge does not fade). A mask that is
    already soft (feathered in PhotoCraft) is returned unchanged."""
    m = mask.convert("L")
    if imaging.is_soft(m):
        return m
    a = np.asarray(m, dtype=np.float32)
    h, w = a.shape
    inside = a > 127
    if not inside.any():
        return m
    if not any(inner):                       # the crop is the whole picture: nothing to fade towards
        return Image.new("L", (w, h), 255)
    big = 1e9
    ys, xs = np.arange(h, dtype=np.float32)[:, None], np.arange(w, dtype=np.float32)[None, :]
    e = np.full((h, w), big, np.float32)     # distance to the nearest side that fades (0 on its last pixel row)
    for on, dist in zip(inner, (xs, ys, w - 1 - xs, h - 1 - ys)):
        if on:
            e = np.minimum(e, np.broadcast_to(dist, (h, w)))
    d = _distance(inside)                    # distance to the selection
    band = min(float(radius), 0.7 * float(e[inside].min()))   # a fade of 30 % of the room at least
    d = np.maximum(d - band, 0.0)
    t = np.clip(e / np.maximum(d + e, 1e-6), 0.0, 1.0)
    fade = t * t * (3.0 - 2.0 * t) * 255.0
    return Image.fromarray(np.maximum(a, fade).round().astype(np.uint8))


def _distance(inside: np.ndarray) -> np.ndarray:
    """Distance in px to the nearest `inside` pixel, at a lower resolution for big crops (the fade is smooth; the
    selection itself is kept exact by the caller)."""
    h, w = inside.shape
    s = max(1, math.ceil(max(w, h) / 400))
    if s == 1:
        return imaging._outside_distance(inside, max(w, h))
    small = np.asarray(Image.fromarray(inside.astype(np.uint8) * 255).resize((max(1, w // s), max(1, h // s)), Image.BOX)) > 127
    sd = imaging._outside_distance(small, max(small.shape)) * s
    return np.asarray(Image.fromarray(sd.astype(np.float32), "F").resize((w, h), Image.BILINEAR))


def layer_mask(variant: str, mask: Image.Image, region: imaging.Box, bbox: imaging.Box, feather_pct: float) -> tuple[Image.Image, int]:
    """The layer mask of `variant` (the size of `region`) and its density in percent."""
    radius = imaging.feather_radius(bbox.w, bbox.h, feather_pct)
    sel = mask.convert("L").crop(region.pil())
    if variant in ("narrow", "density5"):
        return imaging.outer_feather(sel, room(mask.size, region, bbox, radius)), (5 if variant == "density5" else 100)
    if variant == "wide":
        return imaging.outer_feather(sel, room(mask.size, region, bbox, round(radius * WIDE))), 100
    if variant == "crop_fade":
        W, H = mask.size
        inner = (region.x > 0, region.y > 0, region.x + region.w < W, region.y + region.h < H)
        return crop_fade(sel, radius, inner), 100
    raise ValueError(f"unknown variant {variant}")


def effective(mask: Image.Image, density: int) -> Image.Image:
    """What PhotoCraft shows: at density d a masked-out pixel still shows by (100 - d) %."""
    a = np.asarray(mask.convert("L"), dtype=np.float32)
    return Image.fromarray((255.0 - density / 100.0 * (255.0 - a)).round().astype(np.uint8))


def composite(original: Image.Image, result: Image.Image, region: imaging.Box, m: Image.Image, density: int) -> Image.Image:
    """The picture as PhotoCraft shows it: the result (the size of the crop) over the original through the mask."""
    out = original.convert("RGB").copy()
    out.paste(result.convert("RGB").resize((region.w, region.h), Image.LANCZOS), (region.x, region.y), effective(m, density))
    return out
