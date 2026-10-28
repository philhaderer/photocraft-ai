"""Start the bridge window together with PhotoCraft, without a starter .bat (Windows only; user 28.10., option A).

Two parts:
- PhotoCraft reads its control settings from environment variables as well as from the command line
  (PHOTOCRAFT_CONTROL_PORT, PHOTOCRAFT_CONTROL_TOKEN_FILE, PHOTOCRAFT_AUTOMATION_READ_ROOT / _WRITE_ROOT; 0.16 and 0.17).
  `install` sets them for the Windows user, so every start of PhotoCraft opens the control port (taskbar, a double
  click on a file). A starter .bat still works: its command line arguments carry the same values.
- A small watcher without a window (`autostart.pyw`, started at login from the Run key) waits until PhotoCraft's port
  is open and starts the bridge window. The window closes with PhotoCraft (gui.py); the watcher starts it again at the
  next start of PhotoCraft. Closed by hand while PhotoCraft runs, it stays closed until PhotoCraft starts again.
  A bridge window that is already open (started by a .bat) is found by its mutex and not started twice.

    python -m pccomfy autostart install | uninstall | status
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import config as cfgmod

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "autostart.pyw"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "PhotoCraft ComfyUI bridge"
GUI_MUTEX = "Local\\pccomfy-bridge-window"      # held by an open bridge window (gui.run_gui)
WATCH_MUTEX = "Local\\pccomfy-autostart"        # one watcher only
POLL_S = 1.5
GRACE_S = 8.0       # after the port opens: time for a .bat to start its own window first


def env_values(cfg: dict) -> dict[str, str]:
    """The environment variables PhotoCraft needs for the bridge, from the bridge's config."""
    pcc = cfg["photocraft"]
    xch = str(Path(pcc["exchange_dir"]))
    return {"PHOTOCRAFT_CONTROL_PORT": str(int(pcc["port"])),
            "PHOTOCRAFT_CONTROL_TOKEN_FILE": str(Path(pcc["token_file"])),
            "PHOTOCRAFT_AUTOMATION_READ_ROOT": xch,
            "PHOTOCRAFT_AUTOMATION_WRITE_ROOT": xch}


def pythonw() -> str:
    """pythonw.exe next to the interpreter of data\\python.txt (no console window), else next to this one."""
    for py in (_python_txt(), sys.executable):
        if py:
            w = Path(py).with_name("pythonw.exe")
            if w.exists():
                return str(w)
    return sys.executable


def _python_txt() -> str:
    try:
        return (cfgmod.CONFIG_DIR / "python.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def run_command() -> str:
    """The line in the Run key: the watcher, without a console window."""
    return f'"{pythonw()}" "{SCRIPT}"'


# ---------- the watcher ----------

def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class Watcher:
    """One step per poll (pure, so it can be tested): start the window once per PhotoCraft session."""

    def __init__(self, is_open, window_running, launch, clock=time.monotonic):
        self.is_open, self.window_running, self.launch, self.clock = is_open, window_running, launch, clock
        self.seen_at = None     # when the port was first seen open in this PhotoCraft session
        self.done = False       # the window was started (or found) in this session

    def step(self):
        if not self.is_open():
            self.seen_at, self.done = None, False       # PhotoCraft closed: arm again for its next start
            return
        if self.done:
            return
        if self.seen_at is None:
            self.seen_at = self.clock()
        if self.window_running():
            self.done = True                            # a .bat (or the user) opened it already
        elif self.clock() - self.seen_at >= GRACE_S:
            self.launch()
            self.done = True


def _mutex_exists(name: str) -> bool:
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.OpenMutexW.restype = ctypes.c_void_p
    h = k32.OpenMutexW(0x00100000, False, name)      # SYNCHRONIZE
    if h:
        k32.CloseHandle(ctypes.c_void_p(h))
        return True
    return False


def hold_mutex(name: str):
    """Create a named mutex and keep it for the life of the process. None when another process holds it already."""
    if sys.platform != "win32":
        return 1
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    h = k32.CreateMutexW(None, False, name)
    if not h:
        return 1                   # cannot tell: carry on
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        k32.CloseHandle(ctypes.c_void_p(h))
        return None
    return h


def watch():
    if hold_mutex(WATCH_MUTEX) is None:
        return 0                    # a watcher runs already
    cfg = cfgmod.load()
    host, port = cfg["photocraft"]["host"], int(cfg["photocraft"]["port"])

    def launch():
        subprocess.Popen([pythonw(), "-m", "pccomfy"], cwd=str(ROOT), close_fds=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    w = Watcher(lambda: port_open(host, port), lambda: _mutex_exists(GUI_MUTEX), launch)
    while True:
        try:
            w.step()
        except OSError:
            pass
        time.sleep(POLL_S)


# ---------- install / uninstall ----------

def _broadcast_env():
    """Tell Explorer that the environment changed: programs started from now on see the new variables."""
    import ctypes
    res = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(res))


def status(cfg: dict) -> dict:
    import winreg
    out = {"env": {}, "run": None}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        for name in env_values(cfg):
            try:
                out["env"][name] = winreg.QueryValueEx(k, name)[0]
            except FileNotFoundError:
                out["env"][name] = None
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        try:
            out["run"] = winreg.QueryValueEx(k, RUN_NAME)[0]
        except FileNotFoundError:
            pass
    return out


def install(cfg: dict):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        for name, value in env_values(cfg).items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, run_command())
    Path(cfg["photocraft"]["exchange_dir"]).mkdir(parents=True, exist_ok=True)
    _broadcast_env()


def uninstall(cfg: dict):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        for name in env_values(cfg):
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        try:
            winreg.DeleteValue(k, RUN_NAME)
        except FileNotFoundError:
            pass
    _broadcast_env()


def main(action: str, cfg: dict) -> int:
    if sys.platform != "win32":
        print("Only on Windows.")
        return 1
    if action == "install":
        install(cfg)
        print("Installed. Start PhotoCraft as usual (after the next login, or start autostart.pyw once now).")
    elif action == "uninstall":
        uninstall(cfg)
        print("Removed (a watcher that is running stops at the next logout).")
    st = status(cfg)
    for name, value in st["env"].items():
        print(f"  {name} = {value if value is not None else '(not set)'}")
    print(f"  Run at login: {st['run'] or '(not set)'}")
    return 0
