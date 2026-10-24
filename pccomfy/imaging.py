"""Bridge-side image ops: crop with context, scaling, mask preparation, outpaint pre-fill."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def pil(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


def mask_bbox(mask: Image.Image, threshold: int = 3) -> Box | None:
    a = np.asarray(mask.convert("L"))
    ys, xs = np.nonzero(a > threshold)
    if len(xs) == 0:
        return None
    return Box(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def content_box(img: Image.Image, threshold: int = 250, min_band: int = 8) -> Box | None:
    """Bounding box of the real image inside a canvas that was extended around it.

    Empty canvas is transparent (alpha < threshold) or pure white: PhotoCraft's Crop tool fills new canvas with
    white. Only bands along the edges that are empty across the whole image width/height count, and only if they
    are at least `min_band` px thick (a thin white line is not an extension).
    None when there is no such band, or when nothing is left.
    """
    rgba = np.asarray(img.convert("RGBA"))
    empty = (rgba[..., 3] < threshold) | (rgba[..., :3].min(axis=2) >= 254)
    rows, cols = np.flatnonzero(~empty.all(axis=1)), np.flatnonzero(~empty.all(axis=0))
    if len(rows) == 0:
        return None
    W, H = img.size
    x0, x1, y0, y1 = int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1
    x0, y0 = (x0 if x0 >= min_band else 0), (y0 if y0 >= min_band else 0)
    x1, y1 = (x1 if W - x1 >= min_band else W), (y1 if H - y1 >= min_band else H)
    return None if (x0, y0, x1, y1) == (0, 0, W, H) else Box(x0, y0, x1 - x0, y1 - y0)


def clear_outside(img: Image.Image, keep: Box) -> Image.Image:
    """Make everything outside `keep` transparent, so the new canvas gets the edge-extended fill (to_rgb) whether
    the Crop tool left it white or transparent."""
    out = img.convert("RGBA")
    alpha = Image.new("L", out.size, 0)
    alpha.paste(255, keep.pil())
    out.putalpha(alpha)
    return out


def white_outside(img: Image.Image, keep: Box) -> Image.Image:
    """RGB copy with everything outside `keep` flat white, whatever the Crop tool left there (white or transparent)."""
    rgba = img.convert("RGBA")
    out = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    out.paste(Image.alpha_composite(out.crop(keep.pil()), rgba.crop(keep.pil())), (keep.x, keep.y))
    return out.convert("RGB")


def new_area_rect(keep: Box, canvas: tuple[int, int], overlap: int) -> tuple[int, int, int, int]:
    """Rectangle (x0, y0, x1, y1) to subtract from "select all" so the selection is the empty canvas around `keep`
    plus `overlap` px onto the existing image, on every side where canvas was added."""
    W, H = canvas
    ov = max(0, int(overlap))
    x0 = keep.x + (ov if keep.x > 0 else 0)
    y0 = keep.y + (ov if keep.y > 0 else 0)
    x1 = keep.x + keep.w - (ov if keep.x + keep.w < W else 0)
    y1 = keep.y + keep.h - (ov if keep.y + keep.h < H else 0)
    return x0, y0, x1, y1


def grow_box(b: Box, canvas: tuple[int, int], context: float, min_px: int = 32) -> Box:
    """Grow the box by context (fraction of the longer side, at least min_px), clipped to the canvas."""
    W, H = canvas
    pad = max(min_px, int(round(context * max(b.w, b.h))))
    x0, y0 = max(0, b.x - pad), max(0, b.y - pad)
    x1, y1 = min(W, b.x + b.w + pad), min(H, b.y + b.h + pad)
    return Box(x0, y0, x1 - x0, y1 - y0)


def gen_size(w: int, h: int, base: int, multiple: int = 16, max_upscale: float = 2.0) -> tuple[int, int]:
    """Generation size with an area of ~base², the crop's aspect ratio, rounded to a multiple of `multiple`."""
    scale = math.sqrt((base * base) / float(w * h))
    scale = min(scale, max_upscale)
    gw = max(multiple, int(round(w * scale / multiple)) * multiple)
    gh = max(multiple, int(round(h * scale / multiple)) * multiple)
    return gw, gh


def prepare_mask(mask: Image.Image, grow: int, blur: int) -> Image.Image:
    """Mask for the model: grown and blurred a little so the generation overlaps the edge."""
    m = mask.convert("L")
    if grow > 0:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    if blur > 0:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return m


def is_soft(mask: Image.Image) -> bool:
    """True when the mask already has a soft edge (e.g. a selection feathered in PhotoCraft)."""
    a = np.asarray(mask.convert("L"))
    inside = np.count_nonzero(a > 0)
    return inside > 0 and np.count_nonzero((a > 8) & (a < 247)) > 0.01 * inside


def feather_radius(sel_w: int, sel_h: int, percent: float) -> int:
    """Feather width in px: a percentage of the selection's shorter side (0 = hard edge)."""
    return max(0, round(min(sel_w, sel_h) * max(0.0, percent) / 100.0))


def auto_feather(mask: Image.Image, radius: int) -> Image.Image:
    """Soften a hard selection mask by `radius` px. A mask that is already soft is returned unchanged,
    so a feather set in PhotoCraft always wins over the automatic one."""
    m = mask.convert("L")
    if radius <= 0 or is_soft(m):
        return m
    return m.filter(ImageFilter.GaussianBlur(radius / 2.0))


def fill_transparent(img: Image.Image) -> Image.Image:
    """Fill transparent pixels with a blurred extension of the edges (pull–push).

    When outpainting, the new canvas area is transparent; this gives the model plausible colours
    instead of black, which makes the transition much better.
    """
    rgba = np.asarray(img.convert("RGBA")).astype(np.float32) / 255.0
    alpha = rgba[..., 3:4]
    if alpha.min() > 0.99:
        return img.convert("RGB")
    rgb = rgba[..., :3] * alpha
    out = rgba[..., :3].copy()
    known = alpha[..., 0] > 0.99
    h, w = alpha.shape[:2]
    for radius in (2, 8, 32, 128, 512):
        if known.all():
            break
        small = max(1, int(radius / 2))
        sw, sh = max(1, w // small), max(1, h // small)
        # Blur via downscale + Gaussian + upscale (fast for large radii).
        def blur(arr):
            im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
            im = im.resize((sw, sh), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2)).resize((w, h), Image.BILINEAR)
            return np.asarray(im).astype(np.float32) / 255.0
        brgb = blur(rgb)
        ba = blur(alpha[..., 0])[..., None]
        fill = (~known) & (ba[..., 0] > 0.02)
        out[fill] = (brgb / np.maximum(ba, 1e-4))[fill]
        known = known | fill
    out[~known] = rgba[..., :3][known].mean(axis=0) if known.any() else 0.5
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")


def to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        return fill_transparent(img)
    return img.convert("RGB")
