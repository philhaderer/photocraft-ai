"""Where ComfyUI's ``models`` folder is (no Tk here), so a download can go straight into it.

Order: the test override ``PCCOMFY_MODELS_DIR``, the folder you chose once (settings), the folder of the ComfyUI process that
listens on the port the plugin talks to (Windows, PowerShell), else the window asks. ComfyUI's API names no paths.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from pathlib import Path

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def models_dir_of(path: str | Path) -> Path | None:
    """The ``models`` folder for a folder the user (or the process) points at: the ComfyUI folder (main.py and models), the
    folder above it (a portable install), or the models folder itself."""
    p = Path(path)
    for cand in (p, p / "models", p / "ComfyUI" / "models"):
        if cand.name.lower() == "models" and cand.is_dir():
            return cand
    return None


def root_from_process(exe: str, cmdline: str) -> Path | None:
    """The ComfyUI folder (it holds main.py and models) from a running process: an absolute main.py in the command line, else
    the folders above its Python (a portable install starts ``.\\python_embeded\\python.exe ComfyUI\\main.py``)."""
    for tok in (cmdline or "").replace('"', " ").split():
        if tok.lower().endswith("main.py") and os.path.isabs(tok) and Path(tok).exists() and (Path(tok).parent / "models").is_dir():
            return Path(tok).parent
    p = Path(exe or "").parent
    for _ in range(5):
        for cand in (p / "ComfyUI", p):
            if (cand / "main.py").exists() and (cand / "models").is_dir():
                return cand
        if p.parent == p:
            break
        p = p.parent
    return None


def find_root(url: str, timeout: float = 10.0) -> Path | None:
    """The ComfyUI folder of the process that listens on the port of ``url`` (only for a local server), or None."""
    parts = urllib.parse.urlsplit(url)
    if (parts.hostname or "") not in LOCAL_HOSTS or os.name != "nt":
        return None
    port = parts.port or 8188
    script = (f"$c = Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; "
              "if ($c) { Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\" | "
              "Select-Object ExecutablePath, CommandLine | ConvertTo-Json -Compress }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                             timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        info = json.loads(out) if out else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return root_from_process(info.get("ExecutablePath") or "", info.get("CommandLine") or "")
