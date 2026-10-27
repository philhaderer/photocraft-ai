"""The window font: Inter (PhotoCraft's font) ships with its licence, is loaded for this process on Windows and is set
one point smaller than the Segoe UI sizes; without it everything stays Segoe UI. On Windows also a real Tk sees the
families "Inter" and "Inter SemiBold" (on the user's machine Inter is installed as well, so this does not prove the
private loading by itself).

    python tests/test_fonts.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui = t.gui
from pccomfy import fonts, gui_common  # noqa: E402


def main():
    for f in fonts.FILES + ("OFL-Inter.txt",):
        assert (fonts.DIR / f).is_file(), f
    lic = (fonts.DIR / "OFL-Inter.txt").read_text(encoding="utf-8")
    assert "The Inter Project Authors" in lic and "SIL OPEN FONT LICENSE Version 1.1" in lic

    if os.name == "nt":
        assert gui.FONT == "Inter"
    assert gui.font is gui_common.font
    old = gui_common.FONT
    try:
        gui_common.FONT = "Inter"
        assert gui_common.font(9) == ("Inter", 8) and gui_common.font(10, bold=True) == ("Inter SemiBold", 9)
        gui_common.FONT = "Segoe UI"
        assert gui_common.font(9) == ("Segoe UI", 9) and gui_common.font(10, bold=True) == ("Segoe UI", 10, "bold")
    finally:
        gui_common.FONT = old
    os.environ["PCCOMFY_NO_INTER"] = "1"
    assert fonts.load() is False                       # the switch for an A/B look at Segoe UI
    del os.environ["PCCOMFY_NO_INTER"]

    # no font is spelled by hand any more: every place goes through font()
    for p in sorted((t.ROOT / "pccomfy").glob("*.py")):
        text = p.read_text(encoding="utf-8")
        assert "font=(FONT" not in text and '"Segoe UI",' not in text, p.name

    if os.name == "nt":                                # a real Tk in a fresh process (the stub is installed here)
        import subprocess
        code = ("import tkinter as tk, tkinter.font as f; from pccomfy import fonts; fonts.load(); r = tk.Tk(); "
                "fam = set(f.families(r)); r.destroy(); print('Inter' in fam and 'Inter SemiBold' in fam)")
        out = subprocess.run([sys.executable, "-c", code], cwd=t.ROOT, capture_output=True, text=True, timeout=60)
        assert out.stdout.strip() == "True", out.stdout + out.stderr
    print("ok")


if __name__ == "__main__":
    main()
