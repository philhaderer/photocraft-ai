"""Autostart (user 28.10., option A): the bridge window starts with PhotoCraft, without a starter .bat. The watcher starts
it once per PhotoCraft session, waits for a .bat's own window first and never opens a second one; the environment
variables come from the bridge's config. Nothing here touches the registry.

    python tests/test_autostart.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import autostart  # noqa: E402


class Sim:
    def __init__(self):
        self.t, self.open, self.running, self.launched = 0.0, False, False, 0
        self.w = autostart.Watcher(lambda: self.open, lambda: self.running, self.launch, clock=lambda: self.t)

    def launch(self):
        self.launched += 1
        self.running = True

    def wait(self, seconds):
        end = self.t + seconds
        while self.t < end:
            self.w.step()
            self.t += autostart.POLL_S


def watcher_checks():
    s = Sim()
    s.wait(10)
    assert s.launched == 0                       # no PhotoCraft, no window
    s.open = True
    s.wait(autostart.GRACE_S - 2)
    assert s.launched == 0                       # a .bat gets its chance first
    s.wait(4)
    assert s.launched == 1
    s.running = False                            # closed by hand while PhotoCraft runs: stays closed
    s.wait(30)
    assert s.launched == 1
    s.open = False                               # PhotoCraft closed (the window closes with it) ...
    s.wait(3)
    s.open = True                                # ... and started again: the window comes again
    s.wait(autostart.GRACE_S + 2)
    assert s.launched == 2
    # a .bat opened the window: not a second one
    s2 = Sim()
    s2.open = True
    s2.wait(2)
    s2.running = True
    s2.wait(30)
    assert s2.launched == 0


def config_checks():
    tmp = Path(tempfile.mkdtemp())
    cfg = {"photocraft": {"port": 7878, "token_file": str(tmp / "photocraft.token"), "exchange_dir": str(tmp / "exchange")}}
    env = autostart.env_values(cfg)
    assert env == {"PHOTOCRAFT_CONTROL_PORT": "7878",
                   "PHOTOCRAFT_CONTROL_TOKEN_FILE": str(tmp / "photocraft.token"),
                   "PHOTOCRAFT_AUTOMATION_READ_ROOT": str(tmp / "exchange"),
                   "PHOTOCRAFT_AUTOMATION_WRITE_ROOT": str(tmp / "exchange")}
    cmd = autostart.run_command()
    assert str(autostart.SCRIPT) in cmd and autostart.SCRIPT.exists(), cmd
    if sys.platform == "win32":
        assert "pythonw.exe" in cmd.lower(), cmd     # no console window at login
    # the same values as the starter .bat passes on its command line
    bat = (ROOT / "photocraft-ai neuer-nutzer.bat").read_text(encoding="utf-8", errors="replace")
    for flag in ("--control ", "--control-token-file", "--automation-read-root", "--automation-write-root"):
        assert flag in bat, flag


def mutex_checks():
    if sys.platform != "win32":
        return
    name = "Local\\pccomfy-test-" + next(tempfile._get_candidate_names())
    assert not autostart._mutex_exists(name)
    h = autostart.hold_mutex(name)
    assert h and autostart._mutex_exists(name)
    assert autostart.hold_mutex(name) is None     # a second holder is refused (one watcher only)


def cli_checks():
    from pccomfy import __main__ as cli
    called = []
    old = autostart.main
    autostart.main = lambda action, cfg: called.append(action) or 0
    try:
        assert cli.main(["autostart"]) == 0 and cli.main(["autostart", "install"]) == 0
    finally:
        autostart.main = old
    assert called == ["status", "install"]


def main():
    watcher_checks()
    config_checks()
    mutex_checks()
    cli_checks()
    print("ALL OK (autostart)")


if __name__ == "__main__":
    main()
