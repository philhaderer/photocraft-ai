"""Manual check of the REAL Windows clipboard (not part of run_all.py).
Run on Windows:  python tests\\live_clipboard.py
1. It puts a small test picture (orange gradient, transparent corner) on the clipboard. Paste it into PhotoCraft or any
   editor to see it: with "PNG" the corner stays transparent, a plain Windows program shows it white.
2. It reads the clipboard back and prints what it got. Copy any picture first and run it again to test reading."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
from pccomfy import clipboard as cb

if not cb.available():
    raise SystemExit("This check needs Windows.")
img = Image.new("RGBA", (256, 160))
for y in range(160):
    for x in range(256):
        img.putpixel((x, y), (242, 100 + y // 3, 40, 255))
for y in range(40):
    for x in range(40):
        img.putpixel((x, y), (0, 0, 0, 0))
for fmts in (("png", "dib"), ("dib",), ("png",)):
    print(f"write {fmts}: {cb.write_image(img, formats=fmts)}")
cb.write_image(img)                      # leave both formats on the clipboard for pasting
got = cb.read_image()
print("read back:", None if got is None else f"{got.size} {got.mode}")
