"""Start PhotoCraft with the control channel and then the bridge window, like the starter .bat but without a console
window, from a desktop shortcut with PhotoCraft's icon (Windows; user 28.10., option B).

    python -m pccomfy shortcut --photocraft "C:\\programs\\photocraft-0.17.0-windows-x64-portable\\photocraft.exe"

creates the shortcut "PhotoCraft AI" on the desktop; it runs `photocraft-ai.pyw --photocraft <path>` with pythonw.exe.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from . import autostart
from . import config as cfgmod

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "photocraft-ai.pyw"
NAME = "PhotoCraft AI"
WAIT_S = 30.0       # as the .bat: 150 tries of 0.2 s


class LaunchError(Exception):
    pass


def photocraft_args(exe: str, cfg: dict) -> list[str]:
    """The command line the starter .bat uses: control port, token file, the exchange folder for reading and writing."""
    pcc = cfg["photocraft"]
    xch = str(Path(pcc["exchange_dir"]))
    return [exe, "--control", str(int(pcc["port"])), "--control-token-file", str(Path(pcc["token_file"])),
            "--automation-read-root", xch, "--automation-write-root", xch]


def start_photocraft(exe: str, cfg: dict, is_open=None, popen=subprocess.Popen, sleep=time.sleep, wait_s: float = WAIT_S):
    """Start PhotoCraft unless its control port is open already, then wait for the port. Raises LaunchError."""
    pcc = cfg["photocraft"]
    host, port = pcc["host"], int(pcc["port"])
    is_open = is_open or (lambda: autostart.port_open(host, port))
    if is_open():
        return False                      # running with the control channel: only the window is missing
    if not Path(exe).exists():
        raise LaunchError(f"PhotoCraft not found:\n{exe}")
    Path(pcc["exchange_dir"]).mkdir(parents=True, exist_ok=True)
    popen(photocraft_args(exe, cfg), cwd=str(ROOT), close_fds=True)       # as the .bat (cd /d "%~dp0")
    end = time.monotonic() + wait_s
    while time.monotonic() < end:
        if is_open():
            return True
        sleep(0.2)
    raise LaunchError(f"PhotoCraft did not open the control port {port}.\n"
                      "Is another PhotoCraft already running? Close it and start again.")


def launch(exe: str) -> int:
    cfg = cfgmod.load()
    try:
        start_photocraft(exe, cfg)
    except LaunchError as e:
        _error(str(e))
        return 1
    from .gui import run_gui
    return run_gui(cfg)


def _error(text: str):
    """No console: the message in a small dialog."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(NAME, text, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001  (no Tk: nothing more to show)
        pass


# ---------- the shortcut ----------

def shortcut_spec(exe: str, name: str = NAME) -> dict:
    """What the shortcut holds: pythonw.exe runs photocraft-ai.pyw with the PhotoCraft path; PhotoCraft's icon."""
    return {"name": name, "target": autostart.pythonw(), "args": f'"{SCRIPT}" --photocraft "{exe}"',
            "workdir": str(ROOT), "icon": f"{exe},0"}


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create_shortcut(exe: str, name: str = NAME, folder: str | None = None) -> Path:
    """The .lnk on the user's desktop (the real desktop folder, also when OneDrive moves it), via WScript.Shell.
    `folder`: somewhere else instead (the tests)."""
    spec = shortcut_spec(exe, name)
    where = _ps_quote(folder) if folder else "[Environment]::GetFolderPath('Desktop')"
    ps = (f"$d = {where}; "
          f"$p = Join-Path $d ({_ps_quote(spec['name'])} + '.lnk'); "
          "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); "
          f"$s.TargetPath = {_ps_quote(spec['target'])}; $s.Arguments = {_ps_quote(spec['args'])}; "
          f"$s.WorkingDirectory = {_ps_quote(spec['workdir'])}; $s.IconLocation = {_ps_quote(spec['icon'])}; "
          "$s.Description = 'PhotoCraft with the ComfyUI bridge'; $s.Save(); $p")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise LaunchError(out.stderr.strip() or "could not create the shortcut")
    return Path(out.stdout.strip().splitlines()[-1])


def main_shortcut(exe: str, name: str = NAME) -> int:
    if sys.platform != "win32":
        print("Only on Windows.")
        return 1
    if not Path(exe).exists():
        print(f"PhotoCraft not found: {exe}")
        return 1
    try:
        print(f"Created: {create_shortcut(exe, name)}")
    except (LaunchError, OSError, subprocess.SubprocessError) as e:
        print(f"Error: {e}")
        return 1
    return 0
