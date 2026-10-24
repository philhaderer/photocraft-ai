"""Outpaint finds the empty canvas the user opened (Crop tool) and selects it with an overlap.

    python tests/test_outpaint_area.py
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import imaging  # noqa: E402


def canvas(size, content):
    """RGBA image, transparent everywhere except an opaque rectangle (x, y, w, h)."""
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    x, y, w, h = content
    im.paste(Image.new("RGBA", (w, h), (200, 100, 50, 255)), (x, y))
    return im


def main():
    cb = imaging.content_box
    # canvas extended on the right only
    b = cb(canvas((300, 100), (0, 0, 200, 100)))
    assert (b.x, b.y, b.w, b.h) == (0, 0, 200, 100), b
    # extended left and top (what the Crop tool does when dragged outwards)
    b = cb(canvas((280, 160), (80, 60, 200, 100)))
    assert (b.x, b.y, b.w, b.h) == (80, 60, 200, 100), b
    # no empty canvas: opaque RGBA, RGB, nothing opaque
    assert cb(Image.new("RGBA", (50, 50), (1, 2, 3, 255))) is None
    assert cb(Image.new("RGB", (50, 50), (1, 2, 3))) is None
    assert cb(Image.new("RGBA", (50, 50), (0, 0, 0, 0))) is None
    # a soft edge from antialiasing does not count as content
    im = canvas((120, 100), (0, 0, 100, 100))
    im.putpixel((100, 50), (9, 9, 9, 40))
    b = cb(im)
    assert (b.x, b.y, b.w, b.h) == (0, 0, 100, 100), b

    rect = imaging.new_area_rect
    # right only: overlap on the right edge of the original, none on the other sides
    assert rect(imaging.Box(0, 0, 200, 100), (300, 100), 32) == (0, 0, 168, 100)
    # left + top added: overlap on the left/top edges
    assert rect(imaging.Box(80, 60, 200, 100), (280, 160), 16) == (96, 76, 280, 160)
    # all four sides
    assert rect(imaging.Box(50, 50, 200, 100), (300, 200), 10) == (60, 60, 240, 140)
    # overlap larger than the original: empty rectangle (caller skips the subtract)
    x0, y0, x1, y1 = rect(imaging.Box(0, 0, 20, 20), (120, 120), 48)
    assert x1 <= x0 or y1 <= y0
    print("ALL OK")


if __name__ == "__main__":
    main()
