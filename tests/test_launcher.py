"""Desktop shortcut (user 28.10., option B): "PhotoCraft AI" starts PhotoCraft with the control channel like the starter
.bat, then the bridge window, without a console window. The shortcut itself is made in a temporary folder here, never
on the desktop.

    python tests/test_launcher.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import launcher  # noqa: E402

EXE = r"C:\programs\photocraft-0.17.0-windows-x64-portable\photocraft.exe"


def cfg(tmp):
    return {"photocraft": {"host": "127.0.0.1", "port": 7878, "token_file": str(tmp / "photocraft.token"),
                           "exchange_dir": str(tmp / "exchange")}}


def args_checks():
    tmp = Path(tempfile.mkdtemp())
    args = launcher.photocraft_args(EXE, cfg(tmp))
    assert args == [EXE, "--control", "7878", "--control-token-file", str(tmp / "photocraft.token"),
                    "--automation-read-root", str(tmp / "exchange"), "--automation-write-root", str(tmp / "exchange")]
    # the same flags as the starter .bat
    bat = (ROOT / "photocraft-ai neuer-nutzer.bat").read_text(encoding="utf-8", errors="replace")
    for flag in args[1::2]:
        assert flag in bat, flag


def start_checks():
    tmp = Path(tempfile.mkdtemp())
    exe = tmp / "photocraft.exe"
    exe.write_bytes(b"")
    c = cfg(tmp)
    started = []
    # running with the control channel already: nothing is started
    assert launcher.start_photocraft(str(exe), c, is_open=lambda: True, popen=lambda *a, **k: started.append(a)) is False
    assert started == []
    # not running: started once, then the port opens
    state = {"open": False, "polls": 0}

    def is_open():
        state["polls"] += 1
        return state["open"]

    def popen(args, **kw):
        started.append(args)
        state["open"] = True
    assert launcher.start_photocraft(str(exe), c, is_open=is_open, popen=popen, sleep=lambda s: None) is True
    assert started == [launcher.photocraft_args(str(exe), c)] and (tmp / "exchange").is_dir()
    # the port never opens: a clear message
    try:
        launcher.start_photocraft(str(exe), c, is_open=lambda: False, popen=lambda *a, **k: None, sleep=lambda s: None, wait_s=0.05)
        raise AssertionError("no error")
    except launcher.LaunchError as e:
        assert "7878" in str(e)
    # no PhotoCraft at that path
    try:
        launcher.start_photocraft(str(tmp / "missing.exe"), c, is_open=lambda: False)
        raise AssertionError("no error")
    except launcher.LaunchError as e:
        assert "not found" in str(e)


def shortcut_checks():
    spec = launcher.shortcut_spec(EXE)
    assert spec["name"] == "PhotoCraft AI" and spec["icon"] == EXE + ",0"
    assert str(launcher.SCRIPT) in spec["args"] and f'--photocraft "{EXE}"' in spec["args"] and launcher.SCRIPT.exists()
    if sys.platform != "win32":
        return
    assert spec["target"].lower().endswith("pythonw.exe")             # no console window
    folder = tempfile.mkdtemp()
    lnk = launcher.create_shortcut(EXE, folder=folder)
    assert lnk == Path(folder) / "PhotoCraft AI.lnk" and lnk.exists()
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
          "$s.TargetPath; $s.Arguments; $s.IconLocation; $s.WorkingDirectory")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout
    target, args, icon, workdir = out.strip().splitlines()
    assert target.lower() == spec["target"].lower() and args == spec["args"], (target, args)
    assert re.sub(r",\s*0$", "", icon).lower() == EXE.lower() and workdir.lower() == str(launcher.ROOT).lower()


def cli_checks():
    from pccomfy import __main__ as cli
    called = []
    old = launcher.main_shortcut
    launcher.main_shortcut = lambda exe, name: called.append((exe, name)) or 0
    try:
        assert cli.main(["shortcut", "--photocraft", EXE]) == 0
    finally:
        launcher.main_shortcut = old
    assert called == [(EXE, "PhotoCraft AI")]


def main():
    args_checks()
    start_checks()
    shortcut_checks()
    cli_checks()
    print("ALL OK (launcher)")


if __name__ == "__main__":
    main()
