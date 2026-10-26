"""clipboard.py without touching the real clipboard (the Windows calls are replaced).
Run: python tests/test_clipboard.py"""
import io
import struct
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
from pccomfy import clipboard as cb

# a picture with a gradient, a transparent corner and a half-transparent pixel
img = Image.new("RGBA", (6, 4))
for y in range(4):
    for x in range(6):
        img.putpixel((x, y), (x * 40, y * 60, 100, 255))
img.putpixel((0, 0), (10, 20, 30, 0))
img.putpixel((5, 3), (200, 0, 0, 128))

# DIB: a BMP without the 14-byte file header; flat, transparent pixels become white
dib = cb.dib_from_image(img)
assert struct.unpack("<I", dib[:4])[0] == 40 and not dib.startswith(b"BM")
flat = cb.image_from_bytes(dib)
assert flat.size == (6, 4) and flat.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
assert flat.convert("RGB").getpixel((3, 2)) == (120, 120, 100)
assert cb.dib_from_image(Image.new("L", (3, 3), 77))[:4] == struct.pack("<I", 40)       # grey and palette pictures work too

# PNG keeps the transparency
back = cb.image_from_bytes(cb.png_from_image(img)).convert("RGBA")
assert back.getpixel((0, 0))[3] == 0 and back.getpixel((5, 3)) == (200, 0, 0, 128) and back.getpixel((3, 2)) == (120, 120, 100, 255)
assert cb.image_from_bytes(b"not a picture") is None and cb.image_from_bytes(b"") is None

# files copied in Explorer
tmp = Path(tempfile.mkdtemp())
(tmp / "note.txt").write_text("x")
(tmp / "a.PNG").write_bytes(cb.png_from_image(img))
(tmp / "b.jpg").write_bytes(b"\xff\xd8")
(tmp / "dir.png").mkdir()
assert cb.pick_image_file([tmp / "note.txt", tmp / "dir.png", tmp / "missing.png", tmp / "a.PNG", tmp / "b.jpg"]) == tmp / "a.PNG"
assert cb.pick_image_file([tmp / "note.txt"]) is None and cb.pick_image_file([]) is None and cb.pick_image_file(None) is None

# no Windows: nothing happens, nothing raises
cb.available = lambda: False
assert cb.read_image() is None and cb.write_image(img) is False

# Windows path with fake backends
cb.available = lambda: True
calls = []
cb._win_write = lambda items, hwnd=0: calls.append((items, hwnd)) or True
assert cb.write_image(img, hwnd=77) is True
items, hwnd = calls[-1]
assert hwnd == 77 and [f for f, _ in items] == ["PNG", 8] and items[0][1][:8] == b"\x89PNG\r\n\x1a\n" and items[1][1] == dib
assert cb.write_image(img, formats=("dib",)) and [f for f, _ in calls[-1][0]] == [8]
assert cb.write_image(img, formats=()) is False                       # nothing to set
try:
    cb.write_image(img, formats=("gif",))
    raise SystemExit("unknown format must raise")
except ValueError:
    pass
def boom(items, hwnd=0): raise OSError("clipboard locked")
cb._win_write = boom
assert cb.write_image(img) is False                                   # an error from Windows becomes False
cb._win_write = lambda items, hwnd=0: False
assert cb.write_image(img) is False

cb._pillow_grab = lambda: None
cb._win_read_raw = lambda hwnd=0: ("png", cb.png_from_image(img))
assert cb.read_image().convert("RGBA").getpixel((5, 3)) == (200, 0, 0, 128)
cb._win_read_raw = lambda hwnd=0: ("dib", dib)
assert cb.read_image().size == (6, 4)
cb._win_read_raw = lambda hwnd=0: ("dib", b"garbage")                  # unreadable -> Pillow fallback -> nothing
assert cb.read_image() is None
cb._win_read_raw = lambda hwnd=0: None
cb._pillow_grab = lambda: [str(tmp / "note.txt"), str(tmp / "a.PNG")]    # files copied in Explorer
assert cb.read_image().size == (6, 4)
cb._pillow_grab = lambda: Image.new("RGB", (2, 2))
assert cb.read_image().size == (2, 2)
def boom_read(hwnd=0): raise OSError("no clipboard")
cb._win_read_raw = boom_read; cb._pillow_grab = lambda: None
assert cb.read_image() is None
print("test_clipboard ok")
