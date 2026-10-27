"""'Stay with PhotoCraft' in the window (stubbed Tk, faked winlink): link on, unlink off, retries, state on destroy.

    python tests/test_winlink_gui.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402

gui, cfgmod = t.gui, t.cfgmod


def main():
    wl = gui.winlink
    calls = {"link": 0, "unlink": 0}
    found = {"v": False}
    wl.available = lambda: True
    wl.link = lambda root, api=None: (calls.__setitem__("link", calls["link"] + 1), found["v"])[1]
    wl.unlink = lambda root, api=None: calls.__setitem__("unlink", calls["unlink"] + 1)
    wl.owner_present = lambda api=None: True   # else on Windows the real check finds no PhotoCraft and the window quits

    app = gui.App(cfgmod.load())
    scheduled = []
    app.root.after = lambda ms, fn=None, *a: (scheduled.append((ms, fn)), "job")[1]
    app.root.after_cancel = lambda j: None

    def tick():
        ms, fn = scheduled.pop()
        fn()
        return ms

    calls["link"] = calls["unlink"] = 0
    app.v_top.set(True)
    app._on_top()
    assert calls["link"] == 0 and scheduled[-1][0] == 300                    # not at once: Tk's window must exist first
    assert tick() == 300 and calls["link"] == 1 and scheduled[-1][0] == 1500  # not found -> again later
    found["v"] = True
    tick()
    assert calls["link"] == 2 and scheduled[-1][0] == 1500                   # found -> still watched (watchdog)
    app.v_top.set(False)
    app._on_top()
    assert calls["unlink"] == 1
    scheduled.clear()
    app.root.after = lambda ms, fn=None, *a: None
    app._try_link()
    assert calls["link"] == 2                                                # switched off: no more linking

    found["v"] = False
    app.v_top.set(True)
    app._link_tries = 0
    for _ in range(25):
        app._try_link()
    assert "not found" in app.v_status.get()

    class E: widget = app.root
    cfgmod.save_state({})
    app._on_destroy(E())                                                      # owner closed -> state saved once
    assert cfgmod.load_state().get("mode")

    # start position: a first start is placed in PhotoCraft's top right corner at the first link and remembered
    geo = []
    app.root.geometry = lambda g=None: geo.append(g) if g else "380x700+1204+86"
    app.root.winfo_width = lambda: 380
    app.root.state = lambda: "normal"
    wl.owner_rect = lambda api=None: (0, 0, 1600, 900)
    app._placed, app._win_pos = False, None
    app._place_at_owner()
    assert geo == [f"+{1600 - 380 - 16}+{wl.MENU_BAND + 16}"], geo
    app._place_at_owner()
    assert len(geo) == 1                                                     # only once
    app._remember_pos()                                                      # the user moved it: the new place is kept
    assert app._win_pos == (1204, 86)
    cfgmod.save_state({})
    app._closing = False
    app._on_destroy(E())
    assert cfgmod.load_state().get("win_pos") == [1204, 86]
    # the next start uses it (when it is on a screen); one in PhotoCraft's menu bar is moved just below it
    app.state = {"win_pos": [40, 10]}
    wl.on_screen = lambda x, y, api=None: True
    geo.clear()
    app._place_window()
    assert geo == ["+40+10"] and app._placed
    app._place_at_owner()
    assert geo[-1] == f"+40+{wl.MENU_BAND + 16}"
    wl.on_screen = lambda x, y, api=None: False                              # the monitor is gone: placed at PhotoCraft again
    app._place_window()
    assert app._placed is False
    print("ALL OK (winlink gui)")


if __name__ == "__main__":
    main()
