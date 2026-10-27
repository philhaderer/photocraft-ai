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
        self.infos, self.calls, self.owners, self.ready = infos, [], {}, True

    def windows(self):
        return self.infos

    def toplevel(self, root):
        return 777 if self.ready else 0

    def owner_of(self, h):
        return self.owners.get(h, 0)

    def set_owner(self, h, o):
        self.calls.append((h, o))
        self.owners[h] = o


def popup_test():
    pc = r"C:\PhotoCraft\PhotoCraft.exe"
    r = lambda x0, y0, x1, y1: (x0, y0, x1, y1)

    def win(h, rect, exe=pc, visible=True):
        return dict(hwnd=h, exe=exe, visible=visible, rect=rect)
    po = winlink.popups_over
    ours, main_w = 777, 42
    # z-order, topmost first: ours, then a menu below it overlapping, then the main window
    infos = [win(ours, r(0, 0, 100, 100), "py.exe"), win(9, r(50, 50, 200, 200)), win(main_w, r(0, 0, 900, 900))]
    assert po(infos, "photocraft.exe", ours, main_w) == 9
    assert po([win(9, r(50, 50, 200, 200)), win(ours, r(0, 0, 100, 100), "py.exe"), win(main_w, r(0, 0, 900, 900))],
              "photocraft.exe", ours, main_w) is None                       # the menu is already above us
    assert po([win(ours, r(0, 0, 100, 100), "py.exe"), win(9, r(300, 300, 400, 400)), win(main_w, r(0, 0, 900, 900))],
              "photocraft.exe", ours, main_w) is None                       # no overlap
    assert po([win(ours, r(0, 0, 100, 100), "py.exe"), win(9, r(50, 50, 200, 200), "other.exe")],
              "photocraft.exe", ours, main_w) is None                       # another program
    assert po([win(ours, r(0, 0, 100, 100), "py.exe"), win(9, r(50, 50, 200, 200), visible=False)],
              "photocraft.exe", ours, main_w) is None
    infos = [win(ours, r(0, 0, 100, 100), "py.exe"), win(9, r(50, 50, 200, 200)), win(10, r(60, 60, 80, 80)), win(main_w, r(0, 0, 900, 900))]
    assert po(infos, "photocraft.exe", ours, main_w) == 10                  # several: below the lowest

    class F:
        placed = []

        def toplevel(self, root):
            return ours

        def windows(self, everything=False):
            return [dict(win(ours, r(0, 0, 100, 100), "py.exe"), title="bridge"), win(9, r(50, 50, 200, 200)),
                    dict(win(main_w, r(0, 0, 900, 900)), title="PhotoCraft", owner=0, exstyle=0, area=810000)]

        def place_below(self, h, above):
            self.placed.append((h, above))
    f = F()
    assert winlink.yield_to_popups(object(), f) is True and f.placed == [(ours, 9)]


def main():
    popup_test()
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
    assert winlink.link(object(), f) is True and f.calls == [(777, 42)]   # already tied: nothing is set again
    f.owners[777] = 5                                                      # lost (Tk rebuilt its window): tied again
    assert winlink.link(object(), f) is True and f.calls[-1] == (777, 42)
    f = Fake([w(42, pc)])
    f.ready = False                                                        # Tk's window not there yet: later
    assert winlink.link(object(), f) is False and f.calls == []
    f = Fake([w(1, "other.exe")])
    assert winlink.link(object(), f) is False and f.calls == []                          # not found -> free window
    f = Fake([w(42, pc)])
    winlink.unlink(object(), f)
    assert f.calls == [(777, 0)]
    
# menus: a click in the menu bar hides the bridge window while it overlaps the menu area; the next click elsewhere,
# Escape, or leaving PhotoCraft brings it back
owner, win = (0, 0, 1600, 900), (60, 150, 500, 800)
st = {}
st = winlink.menu_step(st, (300, 20), False, False, owner, win)           # hovering: nothing
assert not st["hidden"]
st = winlink.menu_step(st, (300, 20), True, False, owner, win)            # click on a menu
assert st["hidden"]
st = winlink.menu_step(st, (300, 120), False, False, owner, win)          # moving over the open menu
assert st["hidden"]
st = winlink.menu_step(st, (300, 120), True, False, owner, win)           # click on a menu item
assert st["hidden"] is False
st = winlink.menu_step({}, (300, 20), True, False, owner, win)
st = winlink.menu_step(st, (300, 400), False, True, owner, win)           # Escape
assert st["hidden"] is False
st = winlink.menu_step({}, (300, 20), True, False, owner, win)
st = winlink.menu_step(st, (1900, 400), False, False, owner, win)         # pointer left PhotoCraft
assert st["hidden"] is False
far = (60, 800, 500, 880)                                                  # a window below the menu area is left alone
assert not winlink.menu_step({}, (300, 20), True, False, owner, far)["hidden"]
st = winlink.menu_step({"hidden": True, "l": True}, (300, 20), True, False, owner, win)   # button held: no new click
assert st["hidden"]
up = (60, 0, 500, 650)                                                      # the bridge window lies over the menu bar:
assert not winlink.menu_step({}, (300, 20), True, False, owner, up)["hidden"]   # a click on its own title bar is no menu click
assert winlink.menu_step({}, (700, 20), True, False, owner, up)["hidden"]       # a click in the menu bar beside it still is

# start position: first start top right inside PhotoCraft under the menu bar; a saved place in the menu bar moves down
assert winlink.first_position((0, 0, 1600, 900), 380) == (1600 - 380 - 16, winlink.MENU_BAND + 16)
assert winlink.first_position((100, 50, 1700, 950), 570, 1.5) == (1700 - 570 - 24, 50 + round(winlink.MENU_BAND * 1.5) + 24)
assert winlink.below_menu_bar((40, 10), 380, (0, 0, 1600, 900)) == (40, winlink.MENU_BAND + 16)
assert winlink.below_menu_bar((40, 300), 380, (0, 0, 1600, 900)) == (40, 300)          # below the band: stays
assert winlink.below_menu_bar((1700, 10), 380, (0, 0, 1600, 900)) == (1700, 10)        # beside PhotoCraft: stays
print("ALL OK (menu guard)")
print("winlink ok")


if __name__ == "__main__":
    main()
