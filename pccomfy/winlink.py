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

    def windows(self) -> list[dict]:
        out = []

        def cb(hwnd, _):
            try:
                title = self.c.create_unicode_buffer(256)
                self.u.GetWindowTextW(hwnd, title, 256)
                r = self.w.RECT()
                self.u.GetWindowRect(hwnd, self.c.byref(r))
                out.append({"hwnd": int(hwnd), "visible": bool(self.u.IsWindowVisible(hwnd)),
                            "owner": int(self.u.GetWindow(hwnd, GW_OWNER) or 0), "title": title.value,
                            "exstyle": int(self.u.GetWindowLongW(hwnd, GWL_EXSTYLE)), "exe": "",
                            "area": max(0, r.right - r.left) * max(0, r.bottom - r.top)})
            except Exception:
                pass
            return True

        self.u.EnumWindows(self.proto(cb), 0)
        for w in out:   # look up the exe only for plausible candidates
            if w["visible"] and not w["owner"] and w["title"]:
                w["exe"] = self._exe(w["hwnd"])
        return out

    def toplevel(self, root) -> int:
        return int(self.u.GetParent(root.winfo_id()) or root.winfo_id())

    def set_owner(self, hwnd: int, owner: int) -> None:
        self.u.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, owner)


def link(root, api=None) -> bool:
    """Make `root` an owned window of PhotoCraft's main window. False if unavailable or PhotoCraft not found."""
    if not available() and api is None:
        return False
    try:
        api = api or Win32Api()
        owner = pick_window(api.windows(), exe_name())
        if not owner:
            return False
        api.set_owner(api.toplevel(root), owner)
        return True
    except Exception:
        return False


def unlink(root, api=None) -> None:
    if not available() and api is None:
        return
    try:
        api = api or Win32Api()
        api.set_owner(api.toplevel(root), 0)
    except Exception:
        pass
