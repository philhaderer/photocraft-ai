"""The window font: Inter, the font of PhotoCraft itself, shipped in pccomfy/assets/fonts (SIL OFL 1.1, OFL-Inter.txt).

Tk cannot open a font file. On Windows AddFontResourceExW with FR_PRIVATE adds the files for this process only (no
installation, no admin rights); it must run before Tk asks for its first font. When that fails (another system, a
missing file), the window keeps Segoe UI.
"""
from __future__ import annotations

import os
from pathlib import Path

DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FILES = ("Inter-Regular.ttf", "Inter-SemiBold.ttf")    # family "Inter" and "Inter SemiBold" (our bold)
FR_PRIVATE = 0x10


def load() -> bool:
    """Add the Inter files for this process; True when all of them were added."""
    if os.name != "nt" or os.environ.get("PCCOMFY_NO_INTER"):
        return False
    try:
        import ctypes
        add = ctypes.windll.gdi32.AddFontResourceExW
        add.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        return all((DIR / f).exists() and add(str(DIR / f), FR_PRIVATE, None) > 0 for f in FILES)
    except Exception:
        return False
