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

    # PhotoCraft's Crop tool fills new canvas with white
    def white(size, content):
        im = Image.new("RGB", size, (255, 255, 255))
        x, y, w, h = content
        im.paste(Image.new("RGB", (w, h), (200, 100, 50)), (x, y))
        return im

    b = cb(white((300, 100), (0, 0, 200, 100)))
    assert (b.x, b.y, b.w, b.h) == (0, 0, 200, 100), b
    b = cb(white((280, 160), (80, 60, 200, 100)))
    assert (b.x, b.y, b.w, b.h) == (80, 60, 200, 100), b
    # white inside the picture or a thin white line at the edge is not an extension
    im = white((300, 100), (0, 0, 300, 100))
    im.paste(Image.new("RGB", (60, 40), (255, 255, 255)), (100, 30))
    assert cb(im) is None
    assert cb(white((203, 100), (0, 0, 200, 100))) is None
    # white canvas around a picture that has a white sky at the top: only whole empty rows/columns count
    im = white((300, 200), (50, 50, 200, 100))
    b = cb(im)
    assert (b.x, b.y, b.w, b.h) == (50, 50, 200, 100), b
    assert cb(Image.new("RGB", (50, 50), (255, 255, 255))) is None

    # white canvas is turned into the edge-extended fill like a transparent one
    kept = imaging.Box(0, 0, 200, 100)
    filled = imaging.to_rgb(imaging.clear_outside(white((300, 100), (0, 0, 200, 100)), kept))
    px = filled.getpixel((250, 50))
    assert all(abs(a - b) < 30 for a, b in zip(px, (200, 100, 50))), px  # picture colours, not white

    # instruction editors (Fibo): the margin stays flat white, whether the Crop tool left white or transparent
    for im in (white((300, 100), (0, 0, 200, 100)), canvas((300, 100), (0, 0, 200, 100))):
        flat = imaging.white_outside(im, kept)
        assert flat.mode == "RGB" and flat.getpixel((250, 50)) == (255, 255, 255)
        assert flat.getpixel((100, 50)) == (200, 100, 50), flat.getpixel((100, 50))

    from pccomfy import bridge  # noqa: E402
    h = bridge.outpaint_hint(imaging.Box(0, 0, 200, 100), (300, 100))
    assert "on the right of the image" in h and "left" not in h and "leave no white" in h, h
    h = bridge.outpaint_hint(imaging.Box(50, 50, 200, 100), (300, 200))
    assert "left, top, right and bottom" in h, h

    k = imaging.Box(0, 0, 200, 100)
    for enh in (True, False):  # same text with and without the text model
        a = bridge.outpaint_prompt(" a landscape in upper austria ", enh, k, (300, 100))
        assert a.startswith("a landscape in upper austria, replace white (The white margin"), a
        assert bridge.outpaint_prompt("", enh, k, (300, 100)).startswith("Replace white (The white margin")
        b = bridge.outpaint_prompt("a landscape, Replace white", enh, k, (300, 100))
        assert b.startswith("a landscape, Replace white (The white margin") and b.lower().count("replace white") == 1, b
        # Qwen and Flux keep that wording (Qwen Expand is "perfect"); Fibo has its own sentence (A/B test 28.10.)
        for wf in ("qwen-image-21-edit.json", "flux2-klein-edit.json", "flux3-klein-edit.json"):
            assert bridge.outpaint_prompt("", enh, k, (300, 100), wf).startswith("Replace white (The white margin")
        fibo = "C:/x/workflows/fibo2-edit.json"
        assert bridge.outpaint_prompt("", enh, k, (300, 100), fibo) == (
            "Replace the white area on the right with a seamless continuation of the scene. Keep the existing picture unchanged.")
        assert bridge.outpaint_prompt(" a forest path. ", enh, imaging.Box(50, 50, 200, 100), (300, 200), fibo) == (
            "Replace the white area on the left, top, right and bottom with a seamless continuation of the scene, a forest path. "
            "Keep the existing picture unchanged.")

    # the Expand mask: soft only towards the original, black along the original's edges where no canvas was added
    # (PhotoCraft's feather half-selected them; MOSS / Krea 2 painted them anew, 28.10.)
    import numpy as np
    m = np.asarray(imaging.outpaint_mask(imaging.Box(0, 0, 400, 300), (600, 300), 48))
    assert m.shape == (300, 600) and m[150, 0] == 0 and m[0, 100] == 0 and m[299, 100] == 0, "edges without new canvas"
    assert m[0, 599] == 255 and m[150, 420] == 255, "the new canvas"
    assert 100 < m[150, 352] < 155, m[150, 352]                     # half way on the edge 48 px into the original
    assert m[150, 300] == 0 and m[150, 404] == 255                   # the ramp is 2 x 48 px wide
    assert (np.diff(m[150].astype(int)) >= 0).all()                  # rises steadily towards the new canvas
    m = np.asarray(imaging.outpaint_mask(imaging.Box(100, 50, 400, 300), (600, 400), 48))
    assert m[0, 0] == m[399, 599] == 255 and m[200, 300] == 0       # all four sides added: a frame around the original
    assert np.asarray(imaging.outpaint_mask(imaging.Box(0, 0, 600, 300), (600, 300), 48)).max() == 0   # nothing added

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
