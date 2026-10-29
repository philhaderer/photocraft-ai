"""PhotoCraft checkbox: the square draws at 100 % and 150 %, empty = light grey border on a darker field, ticked = orange
with a white tick, greyed out = grey; every TCheckbutton uses it (docs/design/photocraft-checkbox.png).

    python tests/test_checkbox_look.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import gui_common, gui_theme, icons  # noqa: E402


def rgb(im, x, y):
    return im.getpixel((x, y))[:3]


def pixels(im):
    return [im.getpixel((x, y)) for y in range(im.height) for x in range(im.width)]


def near(a, b, tol=12):         # the smooth scaling (LANCZOS) moves a colour a few steps
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def main():
    for px in (gui_theme.CHECK_PX, round(gui_theme.CHECK_PX * 1.5)):
        off = icons.checkbox("#454545", "#a0a0a0", None, px)
        assert off.size == (px, px)
        assert off.getpixel((0, 0))[3] < 255, "rounded corner"
        assert near(rgb(off, px // 2, px // 2), (0x45, 0x45, 0x45)), "dark field inside"
        assert near(rgb(off, 0, px // 2), (0xa0, 0xa0, 0xa0)), "light grey border"
        on = icons.checkbox(gui_common.ACCENT, gui_common.ACCENT, "#ffffff", px)
        assert near(rgb(on, px // 2, round(px * 13.5 / 16)), hexrgb(gui_common.ACCENT)), "filled orange"
        whites = [p for p in pixels(on) if min(p[:3]) > 200]
        assert len(whites) >= px // 2, ("a white tick", len(whites))
        assert not [p for p in pixels(off) if min(p[:3]) > 200], "no tick when empty"
    src = Path(gui_theme.__file__).read_text(encoding="utf-8")
    assert '"PC.Checkbutton.indicator"' in src and 's.layout("TCheckbutton"' in src
    print("test_checkbox_look: ok")


if __name__ == "__main__":
    main()
