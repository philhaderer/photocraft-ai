"""Line icons for the window, drawn with Pillow as vector shapes (no image files, no extra package).

Every icon lives on a 24 x 24 grid with a 2-unit stroke, round ends and round corners, the style of the Lucide icon set
(lucide.dev, ISC licence; the shapes here follow its icons x, scissors, message-square-text, copy, clipboard,
image-plus, plus, settings, undo-2, redo-2, chevron-up/down/right, save and trash-2). An icon is drawn 8 times larger and scaled down with Lanczos to the exact pixel size it is shown at
(display scaling included), so it stays sharp and even at 100 % and at 150 %, which the old 16 px pixel art did not.
"""
from __future__ import annotations

import base64
import io
import math

from PIL import Image, ImageDraw

GRID = 24          # the units the shapes below are written in
STROKE = 2.0       # line width in grid units
SUPER = 8          # drawn this many times larger, then scaled down

Point = tuple[float, float]


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, steps: int = 10) -> list[Point]:
    """Points on a circle from angle a0 to a1 (degrees, 0 = right, 90 = down, as on screen)."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * t / steps)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * t / steps))) for t in range(steps + 1)]


def _circle(cx: float, cy: float, r: float) -> list[Point]:
    return _arc(cx, cy, r, 0, 360, 36)


def _rrect(x: float, y: float, w: float, h: float, r: float) -> list[Point]:
    """A closed rectangle with round corners."""
    return (_arc(x + w - r, y + r, r, 270, 360) + _arc(x + w - r, y + h - r, r, 0, 90)
            + _arc(x + r, y + h - r, r, 90, 180) + _arc(x + r, y + r, r, 180, 270) + [(x + w - r, y)])


# Each icon: a list of open polylines (a closed shape repeats its first point).
SHAPES: dict[str, list[list[Point]]] = {
    "remove": [[(18, 6), (6, 18)], [(6, 6), (18, 18)]],
    "cut": [_circle(6, 6, 3), _circle(6, 18, 3), [(20, 4), (8.12, 15.88)], [(14.47, 14.48), (20, 20)], [(8.12, 8.12), (12, 12)]],
    "describe": [[(21, 15)] + _arc(19, 15, 2, 0, 90) + [(7, 17), (3, 21), (3, 5)] + _arc(5, 5, 2, 180, 270)
                 + _arc(19, 5, 2, 270, 360) + [(21, 15)],
                 [(13, 8), (7, 8)], [(17, 12), (7, 12)]],
    "copy": [_rrect(8, 8, 14, 14, 2),
             [(4, 16)] + _arc(4, 14, 2, 90, 180) + _arc(4, 4, 2, 180, 270) + _arc(14, 4, 2, 270, 360)],
    "paste": [_rrect(8, 2, 8, 4, 1),
              [(16, 4)] + _arc(18, 6, 2, 270, 360) + _arc(18, 20, 2, 0, 90) + _arc(6, 20, 2, 90, 180)
              + _arc(6, 6, 2, 180, 270) + [(8, 4)]],
    "file": [[(16, 5), (22, 5)], [(19, 2), (19, 8)],
             [(21, 11.5)] + _arc(19, 19, 2, 0, 90) + _arc(5, 19, 2, 90, 180) + _arc(5, 5, 2, 180, 270) + [(12.5, 3)],
             [(21, 15), (17.9, 11.9)] + _arc(16.5, 13.3, 2, 315, 225, 6) + [(6, 21)],    # the hill in the picture
             _circle(9, 9, 2)],
}


def _mirror(shape: list[list[Point]]) -> list[list[Point]]:
    return [[(GRID - x, y) for x, y in line] for line in shape]


def _gear(teeth: int = 8, r_out: float = 10.5, r_body: float = 8.0, half_top: float = 8, half_base: float = 14) -> list[list[Point]]:
    """A gear: `teeth` flat teeth (r_out) on a round body (r_body), a hole in the middle."""
    pts: list[Point] = []
    step = 360 / teeth
    for i in range(teeth):
        c = i * step - 90
        pts += _arc(12, 12, r_body, c - half_base, c - half_base, 1)[:1]
        pts += _arc(12, 12, r_out, c - half_top, c + half_top, 3)
        pts += _arc(12, 12, r_body, c + half_base, c + step - half_base, 3)
    return [pts + pts[:1], _circle(12, 12, 3.2)]


_UNDO = [[(9, 14), (4, 9), (9, 4)], [(4, 9), (14.5, 9)] + _arc(14.5, 14.5, 5.5, 270, 450, 12) + [(11, 20)]]
_SAVE = [[(5, 3), (15.2, 3), (21, 8.8), (21, 19)] + _arc(19, 19, 2, 0, 90) + [(5, 21)] + _arc(5, 19, 2, 90, 180)
         + [(3, 5)] + _arc(5, 5, 2, 180, 270)]
SHAPES.update({
    "placeholder": [_rrect(4, 4, 16, 16, 3)],      # a function symbol until the user delivers his own (assets/functions)
    "plus": [[(5, 12), (19, 12)], [(12, 5), (12, 19)]],
    "gear": _gear(),
    "undo": _UNDO,
    "redo": _mirror(_UNDO),
    "chevron-up": [[(6, 15), (12, 9), (18, 15)]],
    "chevron-down": [[(6, 9), (12, 15), (18, 9)]],
    "chevron-right": [[(9, 6), (15, 12), (9, 18)]],
    "save": _SAVE + [[(17, 21), (17, 14), (16, 13), (8, 13), (7, 14), (7, 21)], [(7, 3), (7, 7), (8, 8), (15, 8)]],
    "saveas": _SAVE + [[(13, 14), (13, 20)], [(10, 17), (16, 17)], [(7, 3), (7, 7), (8, 8), (15, 8)]],
    "trash": [[(3, 6), (21, 6)], [(19, 6), (19, 20)] + _arc(17, 20, 2, 0, 90) + [(7, 22)] + _arc(7, 20, 2, 90, 180) + [(5, 6)],
              [(8, 6), (8, 4)] + _arc(10, 4, 2, 180, 270) + [(14, 2)] + _arc(14, 4, 2, 270, 360) + [(16, 6)],
              [(10, 11), (10, 17)], [(14, 11), (14, 17)]],
})


def render(kind: str, color: str, px: int) -> Image.Image:
    """The icon `kind` as an RGBA picture of px x px in `color`."""
    n = px * SUPER
    u = n / GRID
    w = max(1.0, STROKE * u)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for line in SHAPES[kind]:
        pts = [(x * u, y * u) for x, y in line]
        d.line(pts, fill=color, width=round(w))
        for x, y in pts:                     # round ends and joins
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)
    return im.resize((px, px), Image.LANCZOS)


def from_file(path, color: str, px: int) -> Image.Image:
    """A picture file of the user (a function symbol, pccomfy/assets/functions/<key>.png) as an icon in `color`: its
    shape is taken from the alpha channel (or, without transparency, from the dark pixels) and filled with the colour."""
    src = Image.open(path).convert("RGBA")
    alpha = src.getchannel("A")
    if alpha.getextrema() == (255, 255):            # no transparency: dark pixels are the shape
        alpha = src.convert("L").point(lambda v: 255 - v)
    src.thumbnail((px, px), Image.LANCZOS)
    alpha = alpha.resize(src.size, Image.LANCZOS)
    out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    fill = Image.new("RGBA", src.size, color)
    out.paste(fill, ((px - src.width) // 2, (px - src.height) // 2), alpha)
    return out


def spin_arrow(up: bool, color: str, px: int) -> Image.Image:
    """A flat chevron for a spin box: the middle band of the px x px icon (px wide, px / 2 high), so the two arrows stack
    into the height of the field."""
    im = render("chevron-up" if up else "chevron-down", color, px)
    return im.crop((0, px // 4, px, px // 4 + px // 2))


def photo(root, kind: str, color: str, px: int, image: Image.Image | None = None):
    """The icon as a Tk PhotoImage (PNG data); `image` instead of `kind` for a ready picture (spin_arrow)."""
    import tkinter as tk
    buf = io.BytesIO()
    (image if image is not None else render(kind, color, px)).save(buf, "PNG")
    return tk.PhotoImage(master=root, data=base64.b64encode(buf.getvalue()).decode("ascii"))
