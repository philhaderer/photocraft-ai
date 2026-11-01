"""Line icons for the window, drawn with Pillow as vector shapes (no image files, no extra package).

Every icon lives on a 24 x 24 grid with a 2-unit stroke, round ends and round corners, the style of the Lucide icon set
(lucide.dev, ISC licence; the shapes here follow its icons x, scissors, message-square-text, copy, clipboard,
image-plus, plus, settings, undo-2, redo-2, chevron-up/down/right, save, link-2, trash-2 and palette; of the function symbols `fn-multi_edit`
follows images, `fn-upscale` scaling, `fn-refine` focus and `fn-edit` sparkles, the other `fn-` shapes are our own in the
same style). An icon is drawn 8 times larger and scaled down with Lanczos to the exact pixel size it is shown at
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


# the Styles button (Lucide palette): a rounded blob with a thumb notch at the bottom and four paint dots
SHAPES["palette"] = ([_arc(12, 12, 10, 270, 90, 18) + [(13.65, 20.3), (13.2, 18.9), (13.7, 17.7), (15.7, 17.7)]
                      + _arc(15.7, 12.15, 5.55, 90, 0, 6) + _arc(12, 12, 10, 0, -90, 9)]
                     + [[(x, y), (x + 0.01, y)] for x, y in ((13.5, 6.5), (17.5, 10.5), (8.5, 7.5), (6.5, 12.5))])


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
    "placeholder": [_rrect(4, 4, 16, 16, 3)],      # a function without a symbol of its own (img2img)
    "plus": [[(5, 12), (19, 12)], [(12, 5), (12, 19)]],
    "toggle": [_rrect(2, 6, 20, 12, 6), _circle(8, 12, 2.6)],     # a switch: the Easy Mode button in the header
    "toggle-on": [_rrect(2, 6, 20, 12, 6), _circle(16, 12, 2.6)],     # the same switch turned on: the knob on the right
    "gear": _gear(),
    "undo": _UNDO,
    "redo": _mirror(_UNDO),
    "info": [_circle(12, 12, 10), [(12, 16), (12, 11.5)], [(12, 8), (12.01, 8)]],    # a circled i (the tip under the prompt)
    "clock": [_circle(12, 12, 10), [(12, 6), (12, 12), (16, 14)]],     # the last runs (header, history.py)
    "eye":[_arc(12, 15.64, 10.64, 200, 340, 14) + _arc(12, 8.36, 10.64, 20, 160, 14) + [(2, 12)], _circle(12, 12, 3)],
    "seed-last": _mirror([_arc(12, 12, 9, 0, 315, 28) + [(21, 8)], [(21, 3), (21, 8), (16, 8)]]),   # a counter-clockwise circle arrow: use the last seed again
    "refresh":[_arc(12, 12, 9, 0, 315, 28) + [(21, 8)], [(21, 3), (21, 8), (16, 8)]],    # a circle arrow, clockwise
    "minimize": [[(5, 12), (19, 12)]],              # the minimise button in the header
    "close": [[(6, 6), (18, 18)], [(18, 6), (6, 18)]],     # the close button in the header (no title bar)
    "chevron-up": [[(6, 15), (12, 9), (18, 15)]],
    "chevron-down": [[(6, 9), (12, 15), (18, 9)]],
    "chevron-right": [[(9, 6), (15, 12), (9, 18)]],
    # Lucide link-2: two open links and a bar between them (the chain next to a file in the settings window)
    "link": [[(9, 17), (7, 17)] + _arc(7, 12, 5, 90, 270) + [(9, 7)], [(15, 7), (17, 7)] + _arc(17, 12, 5, 270, 450) + [(15, 17)],
             [(8, 12), (16, 12)]],
    "save": _SAVE + [[(17, 21), (17, 14), (16, 13), (8, 13), (7, 14), (7, 21)], [(7, 3), (7, 7), (8, 8), (15, 8)]],
    "saveas": _SAVE + [[(13, 14), (13, 20)], [(10, 17), (16, 17)], [(7, 3), (7, 7), (8, 8), (15, 8)]],
    "trash": [[(3, 6), (21, 6)], [(19, 6), (19, 20)] + _arc(17, 20, 2, 0, 90) + [(7, 22)] + _arc(7, 20, 2, 90, 180) + [(5, 6)],
              [(8, 6), (8, 4)] + _arc(10, 4, 2, 180, 270) + [(14, 2)] + _arc(14, 4, 2, 270, 360) + [(16, 6)],
              [(10, 11), (10, 17)], [(14, 11), (14, 17)]],
})


def _dashed(x0: float, y0: float, x1: float, y1: float, dash: float = 1.6, gap: float = 4.4) -> list[list[Point]]:
    """A dashed rectangle: solid corners, short dashes along the sides (a selection)."""
    c = 2.5
    out = [[(x0, y0 + c), (x0, y0), (x0 + c, y0)], [(x1 - c, y0), (x1, y0), (x1, y0 + c)],
           [(x1, y1 - c), (x1, y1), (x1 - c, y1)], [(x0 + c, y1), (x0, y1), (x0, y1 - c)]]
    for ax, ay, bx, by in [(x0 + c, y0, x1 - c, y0), (x1, y0 + c, x1, y1 - c), (x1 - c, y1, x0 + c, y1), (x0, y1 - c, x0, y0 + c)]:
        length = math.hypot(bx - ax, by - ay)
        n = max(1, round((length - gap) / (dash + gap)))
        step = (length - n * dash) / (n + 1)
        ux, uy = (bx - ax) / length, (by - ay) / length
        for i in range(n):
            s = step * (i + 1) + dash * i
            out.append([(ax + ux * s, ay + uy * s), (ax + ux * (s + dash), ay + uy * (s + dash))])
    return out


def _star(cx: float, cy: float, s: float, inner: float = 0.28) -> list[Point]:
    """A four-pointed spark."""
    pts = [(cx + (s if i % 2 == 0 else s * inner) * math.cos(math.radians(-90 + i * 45)),
            cy + (s if i % 2 == 0 else s * inner) * math.sin(math.radians(-90 + i * 45))) for i in range(8)]
    return pts + pts[:1]


def _plus(cx: float, cy: float, s: float) -> list[list[Point]]:
    return [[(cx - s, cy), (cx + s, cy)], [(cx, cy - s), (cx, cy + s)]]


# the symbols of the function buttons (key = the mode in MODE_LABELS); "fn-" because "remove" above is the X of the
# remove buttons. img2img (only for a workflow of your own) keeps the placeholder.
_FOCUS = [[(3, 7), (3, 5)] + _arc(5, 5, 2, 180, 270) + [(7, 3)], [(17, 3)] + _arc(19, 5, 2, 270, 360) + [(21, 7)],
          [(21, 17)] + _arc(19, 19, 2, 0, 90) + [(17, 21)], [(7, 21)] + _arc(5, 19, 2, 90, 180) + [(3, 17)]]
SHAPES.update({
    "fn-txt2img": [_rrect(3, 3, 18, 18, 2), [(8, 8), (16, 8)], [(12, 8), (12, 17)]],
    "fn-outpaint": [_rrect(8, 8, 8, 8, 1.5)] + _dashed(2, 2, 22, 22),
    "fn-inpaint": _dashed(3, 3, 21, 21) + [_star(12, 12, 5)],
    "fn-remove": _dashed(3, 3, 21, 21) + [[(9, 9), (15, 15)], [(15, 9), (9, 15)]],
    "fn-edit": [_star(10, 13, 7.5, 0.25)] + _plus(19, 5, 2) + _plus(19.5, 18, 1.4),
    "fn-multi_edit": [[(18, 22), (4, 22)] + _arc(4, 20, 2, 90, 180) + [(2, 8)],
                      _rrect(6, 2, 16, 16, 2), [(22, 13), (18, 9), (9, 18)], _circle(11, 7, 1.6)],
    "fn-upscale": [_rrect(3, 13, 8, 8, 1.5), [(13, 11), (21, 3)], [(15, 3), (21, 3), (21, 9)],
                   [(3, 9), (3, 5)] + _arc(5, 5, 2, 180, 270) + [(9, 3)],
                   [(21, 15), (21, 19)] + _arc(19, 19, 2, 0, 90) + [(15, 21)]],
    "fn-refine": _FOCUS + [_circle(12, 12, 3)],
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
    """A flat chevron for a spin box: only the band of the px x px icon the chevron covers (grid rows 7.5 to 16.5 of 24:
    the line from 9 to 15 and its width), so the two arrows stack into the height of the field."""
    im = render("chevron-up" if up else "chevron-down", color, px)
    return im.crop((0, round(px * 7.5 / GRID), px, round(px * 16.5 / GRID)))


def checkbox(fill: str, border: str, check: str | None, px: int) -> Image.Image:
    """A checkbox in PhotoCraft's look (docs/design/photocraft-checkbox.png): a rounded square of px x px with a 2/16
    border; `check` draws the tick (None = empty box). Drawn large and scaled down, so the corners are smooth."""
    n = px * SUPER
    u = n / 16
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=round(3 * u), fill=border)
    d.rounded_rectangle([2 * u, 2 * u, n - 1 - 2 * u, n - 1 - 2 * u], radius=round(1.5 * u), fill=fill)
    if check:
        pts = [(3.6 * u, 8.4 * u), (6.6 * u, 11.2 * u), (12.4 * u, 4.8 * u)]
        w = 2.0 * u
        d.line(pts, fill=check, width=round(w))
        for x, y in pts:                     # round ends and joins
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=check)
    return im.resize((px, px), Image.LANCZOS)


def photo(root, kind: str, color: str, px: int, image: Image.Image | None = None):
    """The icon as a Tk PhotoImage (PNG data); `image` instead of `kind` for a ready picture (spin_arrow)."""
    import tkinter as tk
    buf = io.BytesIO()
    (image if image is not None else render(kind, color, px)).save(buf, "PNG")
    return tk.PhotoImage(master=root, data=base64.b64encode(buf.getvalue()).decode("ascii"))
