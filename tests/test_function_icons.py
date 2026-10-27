"""Function symbols: every function of the head has a shape of its own (fn-<key> in icons.py, img2img keeps the
placeholder), every shape draws at 100 % and 150 %, a picture of the user (assets/functions/<key>.png) still comes first,
and the function buttons show symbol and text left-aligned.

    python tests/test_function_icons.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
from pccomfy import gui_theme, icons  # noqa: E402


class RecStyle(t.Widget):
    seen = {}

    def configure(self, name=None, **k):
        if name is not None:
            RecStyle.seen.setdefault(name, {}).update(k)


def main():
    keys = [k for k, _label in gui.MODE_LABELS if k != "img2img"]
    assert len(keys) == 8, keys
    for k in keys:
        assert f"fn-{k}" in icons.SHAPES, k
        for px in (20, 30):                                     # ICON_PX at 100 % and 150 %
            im = icons.render(f"fn-{k}", "#eeeeee", px)
            assert im.size == (px, px) and im.getbbox() is not None, (k, px)
    assert "fn-img2img" not in icons.SHAPES
    assert icons.SHAPES["remove"] == [[(18, 6), (6, 18)], [(6, 6), (18, 18)]]     # the X of the remove buttons is untouched

    t.ttk.Style = RecStyle
    app = gui.App(cfgmod.load())
    assert RecStyle.seen["Tab.Toolbutton"]["anchor"] == "w"

    # which shape each button asks for: fn-<key>, the placeholder for img2img, the user's picture before both
    asked = []
    real_photo = icons.photo
    icons.photo = lambda root, kind, c, px, image=None: asked.append((kind, image)) or (kind, c)
    try:
        app._icon_cache = {}
        normal, _sel, selected, _dis, disabled = app._function_icon("inpaint")
        assert normal == ("fn-inpaint", gui.FG) and selected == ("fn-inpaint", "#1b1b1b") and disabled[1] == gui.DISABLED
        assert app._function_icon("img2img")[0][0] == "placeholder"
        own = Path(gui_theme.__file__).resolve().parent / "assets" / "functions" / "refine.png"
        made = not own.exists()
        if made:
            own.parent.mkdir(parents=True, exist_ok=True)
            from PIL import Image
            Image.new("RGBA", (40, 40), (0, 0, 0, 255)).save(own)
        try:
            asked.clear()
            app._function_icon("refine")
            assert asked and all(img is not None for _kind, img in asked), asked     # the picture, not the shape
        finally:
            if made:
                own.unlink()
    finally:
        icons.photo = real_photo
    print("ok")


if __name__ == "__main__":
    main()
