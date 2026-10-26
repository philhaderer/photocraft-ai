"""Line icons for the window, drawn with Pillow as vector shapes (no image files, no extra package).

Every icon lives on a 24 x 24 grid with a 2-unit stroke, round ends and round corners, the style of the Lucide icon set
(lucide.dev, ISC licence; the shapes here follow its icons x, scissors, message-square-text, copy, clipboard and
image-plus). An icon is drawn 8 times larger and scaled down with Lanczos to the exact pixel size it is shown at
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


def photo(root, kind: str, color: str, px: int):
    """The icon as a Tk PhotoImage (PNG data)."""
    import tkinter as tk
    buf = io.BytesIO()
    render(kind, color, px).save(buf, "PNG")
    return tk.PhotoImage(master=root, data=base64.b64encode(buf.getvalue()).decode("ascii"))
