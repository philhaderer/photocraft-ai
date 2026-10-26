"""Images on the Windows clipboard: read (Ctrl+V in a slot, Multi Image Edit) and write (Copy canvas to clip).

Pillow is already a dependency; the Windows calls use ctypes, like winlink.py. Everything that does not touch Windows is
pure (`pick_image_file`, `dib_from_image`, `png_from_image`, `image_from_bytes`) and is tested on any system. The two
functions that really talk to the clipboard (`_win_read_raw`, `_win_write`) are tiny so the tests can replace them.

Writing puts two formats on the clipboard: "PNG" (keeps transparency; Photoshop, browsers and most editors read it) and
CF_DIB (flat, understood by every Windows program; transparent areas become white). Reading prefers PNG, then DIB, then
whatever Pillow's ImageGrab finds (a picture, or files copied in Explorer).
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
CF_DIB = 8
GMEM_MOVEABLE = 0x0002
PNG_FORMAT = "PNG"          # the registered clipboard format name that carries real PNG files
DEFAULT_FORMATS = ("png", "dib")


def available() -> bool:
    return sys.platform == "win32"


# ---------- pure helpers ----------

def pick_image_file(paths) -> Path | None:
    """The first path that looks like a picture (files copied in Explorer arrive as a list of paths)."""
    for p in paths or ():
        p = Path(str(p))
        if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file():
            return p
    return None


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def flatten(img: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """RGB copy; transparent areas show `background` (CF_DIB has no usable alpha)."""
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, background)
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return img.convert("RGB")


def dib_from_image(img: Image.Image) -> bytes:
    """The bytes of CF_DIB: a BMP file without its 14-byte file header (starts with BITMAPINFOHEADER)."""
    buf = io.BytesIO()
    flatten(img).save(buf, "BMP")
    return buf.getvalue()[14:]


def png_from_image(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    (img.convert("RGBA") if _has_alpha(img) else img.convert("RGB")).save(buf, "PNG")
    return buf.getvalue()


def image_from_bytes(data: bytes) -> Image.Image | None:
    """PNG bytes or DIB bytes (Pillow reads both) -> a loaded image, or None if it is not a picture."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:
        return None


# ---------- the Windows part ----------

_API = None


def _api():
    """ctypes, user32, kernel32 with argument types set (without them 64-bit handles get cut to 32 bit)."""
    global _API
    if _API is None:
        import ctypes
        from ctypes import wintypes
        user32, kernel32, vp = ctypes.windll.user32, ctypes.windll.kernel32, ctypes.c_void_p
        user32.OpenClipboard.argtypes, user32.OpenClipboard.restype = [vp], wintypes.BOOL
        user32.CloseClipboard.argtypes, user32.CloseClipboard.restype = [], wintypes.BOOL
        user32.EmptyClipboard.argtypes, user32.EmptyClipboard.restype = [], wintypes.BOOL
        user32.SetClipboardData.argtypes, user32.SetClipboardData.restype = [wintypes.UINT, vp], vp
        user32.GetClipboardData.argtypes, user32.GetClipboardData.restype = [wintypes.UINT], vp
        user32.IsClipboardFormatAvailable.argtypes, user32.IsClipboardFormatAvailable.restype = [wintypes.UINT], wintypes.BOOL
        user32.RegisterClipboardFormatW.argtypes, user32.RegisterClipboardFormatW.restype = [wintypes.LPCWSTR], wintypes.UINT
        user32.CreateWindowExA.argtypes = [wintypes.DWORD, wintypes.LPCSTR, wintypes.LPCSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, vp, vp, vp, vp]
        user32.CreateWindowExA.restype = vp
        user32.DestroyWindow.argtypes, user32.DestroyWindow.restype = [vp], wintypes.BOOL
        kernel32.GlobalAlloc.argtypes, kernel32.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], vp
        kernel32.GlobalLock.argtypes, kernel32.GlobalLock.restype = [vp], vp
        kernel32.GlobalUnlock.argtypes, kernel32.GlobalUnlock.restype = [vp], wintypes.BOOL
        kernel32.GlobalSize.argtypes, kernel32.GlobalSize.restype = [vp], ctypes.c_size_t
        kernel32.GlobalFree.argtypes, kernel32.GlobalFree.restype = [vp], vp
        _API = (ctypes, user32, kernel32)
    return _API


def _open(user32, hwnd) -> bool:
    for _ in range(10):         # another program may hold the clipboard for a moment
        if user32.OpenClipboard(hwnd or None):
            return True
        time.sleep(0.02)
    return False


def _win_read_raw(hwnd=0):
    """('png' | 'dib', bytes) of the first of those formats on the clipboard, else None."""
    ctypes, user32, kernel32 = _api()
    if not _open(user32, hwnd):
        return None
    try:
        for name, fmt in (("png", user32.RegisterClipboardFormatW(PNG_FORMAT)), ("dib", CF_DIB)):
            if not user32.IsClipboardFormatAvailable(fmt):
                continue
            handle = user32.GetClipboardData(fmt)
            if not handle:
                continue
            size, ptr = kernel32.GlobalSize(handle), kernel32.GlobalLock(handle)
            if not ptr:
                continue
            try:
                return name, ctypes.string_at(ptr, size)
            finally:
                kernel32.GlobalUnlock(handle)
        return None
    finally:
        user32.CloseClipboard()


def _win_write(items, hwnd=0) -> bool:
    """items: [(format, bytes)], format = a number (CF_DIB) or a registered name ("PNG"). True if at least one was set.
    SetClipboardData needs a window that owns the clipboard: the caller's (Tk) window, or a hidden helper window."""
    ctypes, user32, kernel32 = _api()
    own = None
    if not hwnd:
        own = user32.CreateWindowExA(0, b"STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
        hwnd = own
    try:
        if not _open(user32, hwnd):
            return False
        try:
            user32.EmptyClipboard()
            ok = False
            for fmt, data in items:
                fid = fmt if isinstance(fmt, int) else user32.RegisterClipboardFormatW(fmt)
                handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if not handle:
                    continue
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    kernel32.GlobalFree(handle)
                    continue
                ctypes.memmove(ptr, data, len(data))
                kernel32.GlobalUnlock(handle)
                if user32.SetClipboardData(fid, handle):
                    ok = True                       # the clipboard owns the memory now
                else:
                    kernel32.GlobalFree(handle)
            return ok
        finally:
            user32.CloseClipboard()
    finally:
        if own:
            user32.DestroyWindow(own)


def _pillow_grab():
    """Fallback: Pillow's own reader. An Image, a list of file paths (copied in Explorer) or None."""
    from PIL import ImageGrab
    return ImageGrab.grabclipboard()


# ---------- what the window calls ----------

def read_image(hwnd=0) -> Image.Image | None:
    """The picture on the clipboard (a copied image, a screenshot, or the first picture file copied in Explorer), else None."""
    if not available():
        return None
    try:
        raw = _win_read_raw(hwnd)
        if raw:
            img = image_from_bytes(raw[1])
            if img is not None:
                return img
        got = _pillow_grab()
        if isinstance(got, Image.Image):
            return got
        path = pick_image_file(got) if got else None
        if path is not None:
            with Image.open(path) as f:
                f.load()
                return f.copy()
    except Exception:
        pass
    return None


def write_image(img: Image.Image, formats=DEFAULT_FORMATS, hwnd=0) -> bool:
    """Put the picture on the clipboard as "png" and/or "dib". False if there is no clipboard or nothing could be set."""
    if not available():
        return False
    try:
        items = []
        for f in formats:
            if f == "png":
                items.append((PNG_FORMAT, png_from_image(img)))
            elif f == "dib":
                items.append((CF_DIB, dib_from_image(img)))
            else:
                raise ValueError(f"unknown clipboard format {f!r}")
        return bool(items) and _win_write(items, hwnd)
    except ValueError:
        raise
    except Exception:
        return False
