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


def white_outside(img: Image.Image, keep: Box, color: tuple = (255, 255, 255)) -> Image.Image:
    """RGB copy with everything outside `keep` flat white (or `color`), whatever the Crop tool left there (white or
    transparent)."""
    rgba = img.convert("RGBA")
    out = Image.new("RGBA", rgba.size, tuple(color) + (255,))
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


def outpaint_mask(keep: Box, canvas: tuple[int, int], overlap: int) -> Image.Image:
    """The Expand mask: white on the new canvas plus `overlap` px onto the original, soft only across that inner edge
    (about as wide as PhotoCraft's feather of overlap/2 was there: 2 x overlap, centred on the edge), black on the rest
    of the original right up to the canvas edge where no canvas was added."""
    W, H = canvas
    x0, y0, x1, y1 = new_area_rect(keep, canvas, overlap)
    half = max(1, int(overlap))

    def inside(n: int, lo: int, hi: int, size: int) -> np.ndarray:
        """1 inside [lo, hi), ramping over 2 x half px across an edge that lies inside the canvas, hard at its border."""
        p = np.arange(n) + 0.5
        a = np.clip((p - lo + half) / (2 * half), 0, 1) if lo > 0 else np.ones(n)
        b = np.clip((hi - p + half) / (2 * half), 0, 1) if hi < size else np.ones(n)
        t = np.minimum(a, b)
        return t * t * (3 - 2 * t)          # smoothstep: no hard start or end of the ramp

    if x1 <= x0 or y1 <= y0:
        return Image.new("L", (W, H), 255)
    keep_soft = np.outer(inside(H, y0, y1, H), inside(W, x0, x1, W))
    return Image.fromarray(np.round(255 * (1 - keep_soft)).astype(np.uint8), "L")


def grow_box(b: Box, canvas: tuple[int, int], context: float, min_px: int = 32) -> Box:
    """Grow the box by context (fraction of the longer side, at least min_px), clipped to the canvas."""
    W, H = canvas
    pad = max(min_px, int(round(context * max(b.w, b.h))))
    x0, y0 = max(0, b.x - pad), max(0, b.y - pad)
    x1, y1 = min(W, b.x + b.w + pad), min(H, b.y + b.h + pad)
    return Box(x0, y0, x1 - x0, y1 - y0)


def box_margin_mask(box: Box, canvas: tuple[int, int], margin: float, feather_pct: float) -> Image.Image:
    """Layer mask for a result that may only count around `box`: the box grown by `margin` (share of its width and
    height) on every side, clipped to the canvas, soft edge by `feather_pct` of the grown box's shorter side. Canvas size."""
    W, H = canvas
    dx, dy = round(box.w * margin), round(box.h * margin)
    x0, y0 = max(0, box.x - dx), max(0, box.y - dy)
    x1, y1 = min(W, box.x + box.w + dx), min(H, box.y + box.h + dy)
    m = Image.new("L", (W, H), 0)
    m.paste(255, (x0, y0, x1, y1))
    return auto_feather(m, feather_radius(x1 - x0, y1 - y0, feather_pct))


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


def _outside_distance(inside: np.ndarray, limit: int) -> np.ndarray:
    """Euclidean distance in px from each pixel to the nearest `inside` pixel (0 inside), capped at `limit` + 1.
    Two passes: the distance along each column, then the nearest column within `limit` px (numpy only, no SciPy)."""
    h, w = inside.shape
    cap = float(limit + 1)
    col = np.where(inside, 0.0, cap).astype(np.float32)
    for y in range(1, h):                      # down, then up: distance to the nearest inside pixel in the same column
        np.minimum(col[y], col[y - 1] + 1, out=col[y])
    for y in range(h - 2, -1, -1):
        np.minimum(col[y], col[y + 1] + 1, out=col[y])
    g2 = np.minimum(col, cap) ** 2
    d2 = g2.copy()
    for dx in range(1, min(limit, w - 1) + 1):  # then the nearest of the columns beside it
        np.minimum(d2[:, dx:], g2[:, :-dx] + dx * dx, out=d2[:, dx:])
        np.minimum(d2[:, :-dx], g2[:, dx:] + dx * dx, out=d2[:, :-dx])
    return np.sqrt(d2)


def outer_feather(mask: Image.Image, radius: int) -> Image.Image:
    """Soften a hard selection mask OUTSIDE its edge: inside it stays fully opaque, around it the mask fades out over
    about `radius` px (1 at the edge, ~0.05 at `radius`: the profile twice a Gaussian blur of half the radius gives a
    straight edge). Used for Fill with an instruction editor: the new object keeps its full outline, only the redrawn
    surroundings blend in. The fade follows the distance to the selection, so a corner fades as wide as an edge
    (the blur alone gave a rectangle hard corners, live test 28.10.). A mask that is already soft is returned
    unchanged, as in auto_feather."""
    m = mask.convert("L")
    if radius <= 0 or is_soft(m):
        return m
    a = np.asarray(m, dtype=np.float32)
    limit = int(radius * 1.3)                  # cut off beyond 1.3 × radius (below 1 %), where the blur ended too
    d = _outside_distance(a > 127, limit)
    sigma = radius / 2.0
    xs = np.arange(0, limit + 2, 0.25)
    table = np.array([1.0 - math.erf(x / (sigma * math.sqrt(2.0))) for x in xs])   # = 2 × (1 - Phi(x / sigma))
    b = np.interp(np.maximum(d - 0.5, 0.0), xs, table) * 255.0   # measured from the pixel's edge, as the blur was
    b[d > limit] = 0.0
    return Image.fromarray(np.maximum(a, np.minimum(255.0, b)).round().astype(np.uint8))


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


def sharpen(im: Image.Image, amount: float) -> Image.Image:
    """A light sharpening: amount 0 = none, 1 = strong. Unsharp mask (the same idea as a high-pass sharpen)."""
    if amount <= 0:
        return im
    from PIL import ImageFilter
    r = max(1.0, max(im.size) / 1000)   # the radius follows the picture size
    return im.filter(ImageFilter.UnsharpMask(radius=r, percent=int(min(1.0, amount) * 150), threshold=2))


def match_outside(gen: Image.Image, ref: Image.Image, outside: Image.Image, max_ratio: float = 1.25) -> Image.Image:
    """BBOX: the model redrew the whole picture with slightly different colours, but only the box zone is used. Per channel,
    brightness and contrast of `gen` are fitted (mean and spread, spread ratio kept within 1/max_ratio..max_ratio) so that the
    part beyond the box zone (`outside`, white = reference pixels) matches the original `ref` there; applied to all of `gen`.
    Returns `gen` unchanged when the reference part is too small (< 5 % of the picture)."""
    size = gen.size
    o = np.asarray(outside.convert("L").resize(size, Image.NEAREST)) > 127
    if o.mean() < 0.05:
        return gen
    g = np.asarray(gen.convert("RGB"), dtype=np.float32)
    r = np.asarray(ref.convert("RGB").resize(size, Image.BILINEAR), dtype=np.float32)
    out = g.copy()
    for c in range(3):
        gm, gs = float(g[..., c][o].mean()), float(g[..., c][o].std())
        rm, rs = float(r[..., c][o].mean()), float(r[..., c][o].std())
        k = min(max_ratio, max(1.0 / max_ratio, rs / gs)) if gs > 1.0 else 1.0
        out[..., c] = (g[..., c] - gm) * k + rm
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")


def match_saturation(gen: Image.Image, ref: Image.Image, mask: Image.Image, strength: float) -> Image.Image:
    """Tames colours that are louder than their surroundings: the new area (`mask`, white = new) is compared with a ring of
    the original picture (`ref`) around it, by the mean HSV saturation. If the new area is more saturated, the saturation
    of `gen` is scaled down towards the ring's (never below half, and never up). `strength` 0 = off, 1 = all the way.
    Returns `gen` unchanged when there is no usable ring."""
    if strength <= 0:
        return gen
    size = gen.size
    ref = ref.convert("RGB").resize(size, Image.BILINEAR)
    m = np.asarray(mask.convert("L").resize(size, Image.BILINEAR)) > 128
    if m.sum() < 64:
        return gen
    from PIL import ImageFilter
    r = max(6.0, 0.06 * min(size))
    near = np.asarray(mask.convert("L").resize(size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(r))) > 6
    ring = near & ~m
    if ring.sum() < 64:
        return gen
    g_s = np.asarray(gen.convert("RGB").convert("HSV"))[..., 1].astype(float)
    r_s = np.asarray(ref.convert("HSV"))[..., 1].astype(float)
    inside, around = float(g_s[m].mean()), float(r_s[ring].mean())
    if inside <= around or inside < 1:
        return gen
    f = max(0.5, around / inside)
    k = 1.0 - min(1.0, strength) * (1.0 - f)
    h, sat, v = gen.convert("RGB").convert("HSV").split()
    return Image.merge("HSV", (h, sat.point(lambda x: min(255, int(x * k + 0.5))), v)).convert("RGB")


SEAM_OUTLIER = 40.0    # levels: a difference this large is a changed object (a shadow, a new edge), not a tone shift


def _seam_parts(gen: Image.Image, ref: Image.Image, mask: Image.Image):
    """What the seam correction works with, all at the size of `gen`: the difference ref - gen (float RGB), the weight of
    each pixel (1 where the result must match the original: outside the new area and not a changed object) and the ring
    just outside the new area where the seam is measured. None when there is not enough to measure."""
    size = gen.size
    g = np.asarray(gen.convert("RGB"), dtype=np.float32)
    r = np.asarray(ref.convert("RGB").resize(size, Image.BILINEAR), dtype=np.float32)
    m = np.asarray(mask.convert("L").resize(size, Image.BILINEAR))
    new, known = m > 127, m < 8           # (Expand: the soft overlap between them counts as neither)
    if new.sum() < 64 or known.sum() < 64:
        return None
    diff = r - g
    lum = np.abs(diff @ np.array([0.299, 0.587, 0.114], dtype=np.float32))
    w = (known & (lum < SEAM_OUTLIER)).astype(np.float32)
    if w.sum() < 64:
        return None
    band = max(3.0, 0.03 * min(size))
    near = np.asarray(Image.fromarray((new * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(band))) > 6
    ring = near & known
    return diff, w, ring


def _smooth_field(diff: np.ndarray, w: np.ndarray, sigma: float) -> np.ndarray:
    """The weighted difference, blurred: a smooth correction for every pixel. Where no measured pixel lies near (deep
    inside a large selection) the next wider blur fills in, at last the overall mean (as fill_transparent does)."""
    h, wd = w.shape

    def blur(a: np.ndarray, s: float) -> np.ndarray:
        k = max(1, int(s / 2))           # downscale + Gaussian + upscale: fast for large radii (Pillow cannot blur
        sw, sh = max(1, wd // k), max(1, h // k)     # float images, so the small one is blurred with numpy)
        small = np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((sw, sh), Image.BILINEAR), dtype=np.float32)
        ss = max(0.5, s / k)
        x = np.arange(-int(3 * ss), int(3 * ss) + 1, dtype=np.float32)
        kern = np.exp(-0.5 * (x / ss) ** 2)
        kern /= kern.sum()
        n = len(x) // 2
        for axis in (0, 1):
            p = np.pad(small, [(n, n) if ax == axis else (0, 0) for ax in (0, 1)], mode="edge")
            small = sum(kern[i] * np.take(p, range(i, i + small.shape[axis]), axis=axis) for i in range(len(x)))
        return np.asarray(Image.fromarray(small.astype(np.float32), "F").resize((wd, h), Image.BILINEAR), dtype=np.float32)

    out = np.zeros_like(diff)
    done = np.zeros((h, wd), bool)
    s = sigma
    while not done.all() and s < 4 * max(h, wd):
        bw = blur(w, s)
        ok = (bw > 0.05) & ~done
        if ok.any():
            for c in range(3):
                out[..., c][ok] = (blur(diff[..., c] * w, s) / np.maximum(bw, 1e-4))[ok]
            done |= ok
        s *= 2
    if not done.all():
        mean = (diff * w[..., None]).sum((0, 1)) / max(1.0, float(w.sum()))
        out[~done] = mean
    return out


def seam_jump(gen: Image.Image, ref: Image.Image, mask: Image.Image) -> float:
    """The tone jump at the seam in levels (0..255): the smoothed brightness difference between the result and the
    original, averaged over a ring just outside the new area. 0 when there is nothing to measure."""
    parts = _seam_parts(gen, ref, mask)
    if parts is None:
        return 0.0
    diff, w, ring = parts
    if not ring.any():
        return 0.0
    field = _smooth_field(diff, w, max(4.0, 0.04 * min(gen.size)))
    lum = field @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return float(np.abs(lum[ring]).mean())


def seam_correct(gen: Image.Image, ref: Image.Image, mask: Image.Image) -> Image.Image:
    """Seam correction (OpenFill's idea, T2): where the result must match the original (outside the new area, `mask`
    white = new) the tone difference is measured, smoothed and added to the whole result, so the redrawn surroundings
    meet the original without a lighter or darker rim. Only the smooth part changes: the detail stays as the model drew
    it, a geometric shift is not corrected. Returns `gen` unchanged when there is nothing to measure."""
    parts = _seam_parts(gen, ref, mask)
    if parts is None:
        return gen
    diff, w, _ring = parts
    field = _smooth_field(diff, w, max(4.0, 0.04 * min(gen.size)))
    g = np.asarray(gen.convert("RGB"), dtype=np.float32)
    return Image.fromarray(np.clip(g + field, 0, 255).round().astype(np.uint8), "RGB")


def layer_box(layer: Image.Image) -> "Box | None":
    """Where a layer's visible pixels lie on the canvas (the layer exported at canvas size), or None when it is empty."""
    box = layer.convert("RGBA").getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return Box(box[0], box[1], box[2] - box[0], box[3] - box[1]) if box else None


def mark_outline(img: Image.Image, mask: Image.Image, width: int = 4, color: tuple[int, int, int] = (255, 0, 0)) -> Image.Image:
    """Draw the outline of the selection (`mask`, same size as `img`) into a copy of `img`: a line `width` px thick on
    each side of the edge. Instruction-based editors (Fibo) cannot read a mask, but they can see a coloured outline."""
    width = max(1, int(width))
    img = img.convert("RGB")
    m = mask.convert("L").resize(img.size, Image.NEAREST).point(lambda v: 255 if v > 127 else 0)
    size = 2 * width + 1
    ring = np.asarray(m.filter(ImageFilter.MaxFilter(size))).astype(int) - np.asarray(m.filter(ImageFilter.MinFilter(size))).astype(int)
    out = np.array(img)
    out[ring > 0] = color
    return Image.fromarray(out)


def removal_score(before: Image.Image, after: Image.Image, mask: Image.Image, width: int) -> float:
    """How much of the selection was really replaced (0..1; 0 when the red outline is still there). Measured on
    live tests: failed removals 0 to 0.11, successful ones 0.16 and up. `before` is the picture sent (without the
    red outline), `after` the result, `mask` the selection (all in the generated size), `width` the outline's half
    thickness. Low = the area is practically unchanged (the model only wiped the outline and kept the object)."""
    after = after.convert("RGB").resize(before.size, Image.BILINEAR)
    m = mask.convert("L").resize(before.size, Image.NEAREST).point(lambda v: 255 if v > 127 else 0)
    small = m.resize((max(1, m.width // 4), max(1, m.height // 4)), Image.NEAREST)
    k = max(1, (2 * width) // 4)
    inner = np.asarray(small.filter(ImageFilter.MinFilter(2 * k + 1))) > 0   # without the outline's own pixels
    if not inner.any():
        inner = np.asarray(small) > 0
    b = np.asarray(before.convert("RGB").resize(small.size, Image.BILINEAR)).astype(int)
    a = np.asarray(after.resize(small.size, Image.BILINEAR)).astype(int)
    changed = (np.abs(a - b).max(axis=2) > 40)[inner].mean() if inner.any() else 1.0
    size = 2 * max(1, int(width)) + 1
    ring = (np.asarray(m.filter(ImageFilter.MaxFilter(size))).astype(int) - np.asarray(m.filter(ImageFilter.MinFilter(size))).astype(int)) > 0
    arr = np.asarray(after).astype(int)
    red = (arr[..., 0] > 200) & (arr[..., 1] < 70) & (arr[..., 2] < 70)
    outline_left = ring.any() and red[ring].mean() > 0.25
    return 0.0 if outline_left else float(changed)


REMOVAL_MIN = 0.13   # between the failed (<= 0.11) and the successful (>= 0.16) live tests


def removal_done(before: Image.Image, after: Image.Image, mask: Image.Image, width: int, min_changed: float = REMOVAL_MIN) -> bool:
    """True when `removal_score` says the selection was replaced."""
    return removal_score(before, after, mask, width) >= min_changed
