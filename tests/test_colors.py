"""Colours: the inactive tab / field colour (PANEL) is one constant, a tab that is not available is red on that background,
nothing in the sources spells the old colour by hand, and text on PANEL stays readable.

    python tests/test_colors.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
ROOT = t.ROOT


def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


class RecStyle(t.Widget):
    seen = {}

    def configure(self, name=None, **k):
        if name is not None:
            RecStyle.seen.setdefault(name, {}).update(k)


def main():
    assert gui.PANEL == "#282828" and gui.NA_RED == "#ff6b6b"
    # readable on PANEL (WCAG AA for normal text is 4.5; DISABLED is 4.5 to one decimal)
    for name in ("FG", "MUTED", "ACCENT_TEXT", "NA_RED", "ERROR_TEXT", "DONE_GREEN"):
        assert contrast(getattr(gui, name), gui.PANEL) >= 4.5, name
    assert contrast(gui.DISABLED, gui.PANEL) >= 4.45

    # the old colour is not spelled by hand anywhere (gui.py's title-bar colour is the one known exception, see FRAGEN)
    for p in sorted((ROOT / "pccomfy").glob("*.py")):
        text = p.read_text(encoding="utf-8").lower()
        if p.name == "gui.py":
            continue
        assert "#404040" not in text and "0x40, 0x40, 0x40" not in text, p.name

    # the tab styles: inactive = PANEL, not available = red text and no other background of its own
    t.ttk.Style = RecStyle
    gui.App(cfgmod.load())
    s = RecStyle.seen
    assert s["Tab.Toolbutton"]["background"] == gui.PANEL
    assert s["Missing.Chip.Toolbutton"] == {"foreground": gui.NA_RED}, s["Missing.Chip.Toolbutton"]
    print("ok")


if __name__ == "__main__":
    main()
