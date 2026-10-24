"""Window linking: picking PhotoCraft's main window and (un)linking through a fake API.

    python tests/test_winlink.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import winlink  # noqa: E402


def w(hwnd, exe, title="x", visible=True, owner=0, exstyle=0, area=100):
    return dict(hwnd=hwnd, exe=exe, title=title, visible=visible, owner=owner, exstyle=exstyle, area=area)


class Fake:
    def __init__(self, infos):
        self.infos, self.calls = infos, []

    def windows(self):
        return self.infos

    def toplevel(self, root):
        return 777

    def set_owner(self, h, o):
        self.calls.append((h, o))


def main():
    pick = winlink.pick_window
    pc = r"C:\Program Files\PhotoCraft\PhotoCraft.exe"
    assert pick([w(1, pc), w(2, r"C:\x\other.exe", area=999)], "photocraft.exe") == 1
    assert pick([w(1, pc, area=10), w(2, pc, area=500)], "photocraft.exe") == 2          # largest wins
    assert pick([w(1, pc, visible=False)], "photocraft.exe") is None
    assert pick([w(1, pc, owner=5)], "photocraft.exe") is None                           # owned = not the main window
    assert pick([w(1, pc, title="")], "photocraft.exe") is None
    assert pick([w(1, pc, exstyle=winlink.WS_EX_TOOLWINDOW)], "photocraft.exe") is None
    assert pick([w(1, "PHOTOCRAFT.EXE")], "photocraft.exe") == 1                         # case-insensitive
    assert pick([], "photocraft.exe") is None

    f = Fake([w(42, pc)])
    assert winlink.link(object(), f) is True and f.calls == [(777, 42)]
    f = Fake([w(1, "other.exe")])
    assert winlink.link(object(), f) is False and f.calls == []                          # not found -> free window
    f = Fake([w(42, pc)])
    winlink.unlink(object(), f)
    assert f.calls == [(777, 0)]
    print("winlink ok")


if __name__ == "__main__":
    main()
