"""Tie the bridge window to PhotoCraft's main window (Windows only).

An *owned* window in Windows minimizes and restores together with its owner, stays above its owner only
(not above other programs) and is destroyed with it. That is exactly "the plugin belongs to PhotoCraft".

The window search is kept pure (`pick_window`) so it can be tested without Windows.
"""
from __future__ import annotations

import os
import sys

DEFAULT_EXE = "photocraft.exe"
GWLP_HWNDPARENT = -8
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


def available() -> bool:
    return sys.platform == "win32"


def exe_name() -> str:
    return (os.environ.get("PCC_PHOTOCRAFT_EXE") or DEFAULT_EXE).lower()


def pick_window(infos: list[dict], exe: str) -> int | None:
    """infos: dicts with hwnd, visible, owner, title, exstyle, exe (path or name), area. Largest matching window wins."""
    exe = exe.lower()
    best, best_area = None, -1
    for w in infos:
        if not w.get("visible") or w.get("owner") or not w.get("title"):
            continue
        if w.get("exstyle", 0) & WS_EX_TOOLWINDOW:
            continue
        name = os.path.basename((w.get("exe") or "").replace("\\", "/")).lower()
        if name != exe:
            continue
        if w.get("area", 0) > best_area:
            best, best_area = w["hwnd"], w.get("area", 0)
    return best


class Win32Api:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.c, self.w = ctypes, wintypes
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        self.u, self.k = u, k
        self.proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindow.restype = wintypes.HWND
        u.GetParent.restype = wintypes.HWND
        u.GetAncestor.restype = wintypes.HWND
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        k.OpenProcess.restype = wintypes.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        u.SetWindowLongPtrW.restype = ctypes.c_void_p

    def _exe(self, hwnd) -> str:
        pid = self.w.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, self.c.byref(pid))
        h = self.k.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = self.c.create_unicode_buffer(1024)
            n = self.w.DWORD(1024)
            return buf.value if self.k.QueryFullProcessImageNameW(h, 0, buf, self.c.byref(n)) else ""
        finally:
            self.k.CloseHandle(h)

    def windows(self, everything: bool = False) -> list[dict]:
        out = []

        def cb(hwnd, _):
            try:
                title = self.c.create_unicode_buffer(256)
                self.u.GetWindowTextW(hwnd, title, 256)
                r = self.w.RECT()
                self.u.GetWindowRect(hwnd, self.c.byref(r))
                cls = self.c.create_unicode_buffer(128)
                self.u.GetClassNameW(hwnd, cls, 128)
                out.append({"class": cls.value, "iconic": bool(self.u.IsIconic(hwnd)),
                            "rect": (r.left, r.top, r.right, r.bottom), "hwnd": int(hwnd), "visible": bool(self.u.IsWindowVisible(hwnd)),
                            "owner": int(self.u.GetWindow(hwnd, GW_OWNER) or 0), "title": title.value,
                            "exstyle": int(self.u.GetWindowLongW(hwnd, GWL_EXSTYLE)), "exe": "",
                            "area": max(0, r.right - r.left) * max(0, r.bottom - r.top)})
            except Exception:
                pass
            return True

        self.u.EnumWindows(self.proto(cb), 0)
        for w in out:   # look up the exe only for plausible candidates (all of them with `everything`)
            if everything or (w["visible"] and not w["owner"] and w["title"]):
                w["exe"] = self._exe(w["hwnd"])
        return out

    def toplevel(self, root) -> int:
        """The real top-level window of a Tk root (the "TkTopLevel" wrapper around Tk's inner window), or 0 while Tk
        has not created it yet (before the first update): the inner window must never be touched."""
        root.update_idletasks()
        top = self.u.GetAncestor(root.winfo_id(), 2)   # GA_ROOT
        cls = self.c.create_unicode_buffer(64)
        if top:
            self.u.GetClassNameW(top, cls, 64)
        return int(top) if top and cls.value == "TkTopLevel" else 0

    def owner_of(self, hwnd: int) -> int:
        return int(self.u.GetWindow(hwnd, GW_OWNER) or 0)

    def set_owner(self, hwnd: int, owner: int) -> None:
        self.u.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, owner)

    def place_below(self, hwnd: int, above: int) -> None:
        """Put `hwnd` directly below `above` in the z-order, without moving, resizing or activating it."""
        self.u.SetWindowPos(hwnd, above, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)   # NOSIZE | NOMOVE | NOACTIVATE


def link(root, api=None) -> bool:
    """Make `root` an owned window of PhotoCraft's main window and check that it took. True = tied to PhotoCraft now.
    Idempotent (nothing is set when the owner is already right), so it can run again and again as a watchdog.
    False: not on Windows, PhotoCraft not found, or Tk's window not created yet: try again later."""
    if not available() and api is None:
        return False
    try:
        api = api or Win32Api()
        owner = pick_window(api.windows(), exe_name())
        top = api.toplevel(root)
        if not owner or not top:
            return False
        if api.owner_of(top) != owner:
            api.set_owner(top, owner)
        return api.owner_of(top) == owner
    except Exception:
        return False


def popups_over(infos: list[dict], exe: str, top: int, owner: int | None) -> int | None:
    """infos in z-order, topmost first (EnumWindows order). Returns the popup of PhotoCraft's process (a menu, a drop-down,
    a tooltip) that lies BELOW the bridge window `top` and overlaps it - the one the bridge window must give way to - or
    None. When several qualify, the lowest one: the bridge window then goes below all of them."""
    exe = exe.lower()
    mine = None
    found = None
    for w in infos:
        if w.get("hwnd") == top:
            mine = w
            continue
        if mine is None or not w.get("visible"):
            continue
        name = os.path.basename((w.get("exe") or "").replace("\\", "/")).lower()
        if name != exe or w["hwnd"] == owner:
            continue
        a, b = mine.get("rect"), w.get("rect")
        if a and b and (b[0] >= a[2] or b[2] <= a[0] or b[1] >= a[3] or b[3] <= a[1]):
            continue   # no overlap with the bridge window
        found = w["hwnd"]
    return found


def yield_to_popups(root, api=None) -> bool:
    """PhotoCraft's menus open above the main window, but an owned window that was active last can still cover them.
    Called often (a few times per second): when a popup of PhotoCraft lies below the bridge window and overlaps it, the
    bridge window is put directly below that popup. True = something was moved."""
    if not available() and api is None:
        return False
    try:
        api = api or Win32Api()
        top = api.toplevel(root)
        infos = api.windows(everything=True)
        owner = pick_window(infos, exe_name())
        if not top or not owner:
            return False
        over = popups_over(infos, exe_name(), top, owner)
        if over is None:
            return False
        api.place_below(top, over)
        return True
    except Exception:
        return False


def unlink(root, api=None) -> None:
    if not available() and api is None:
        return
    try:
        api = api or Win32Api()
        top = api.toplevel(root)
        if top:
            api.set_owner(top, 0)
    except Exception:
        pass


def describe(api=None) -> str:
    """Debug: every window of PhotoCraft's process and which one the bridge window would be tied to."""
    api = api or Win32Api()
    infos = api.windows(everything=True)
    exe = exe_name()
    mine = [w for w in infos if os.path.basename((w.get("exe") or "").replace("\\", "/")).lower() == exe]
    pick = pick_window(infos, exe)
    lines = [f"Windows of {exe}: {len(mine)}  (chosen: {pick})"]
    for w in sorted(mine, key=lambda w: -w.get("area", 0)):
        lines.append(f"{'->' if w['hwnd'] == pick else '  '} hwnd={w['hwnd']} class={w.get('class')!r} title={w['title']!r} "
                     f"visible={w['visible']} iconic={w.get('iconic')} owner={w['owner']} exstyle={w['exstyle']:#x} "
                     f"rect={w.get('rect')} area={w.get('area')}")
    if not mine:
        lines.append("None found. Is PhotoCraft running? Another program name: set PCC_PHOTOCRAFT_EXE=name.exe")
    return "\n".join(lines)
