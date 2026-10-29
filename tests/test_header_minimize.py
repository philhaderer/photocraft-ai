"""Header with the minimise button (option A of the user, 29.10.): minimised, only the header stays (functions, models,
body, status and footer go); a second click brings them back, and a start-state change meanwhile does not unpack them.

    python tests/test_header_minimize.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod


def main():
    binds = []
    t.Widget.bind = lambda self, seq, fn=None, add=None: binds.append((self, seq, fn))
    try:
        app = gui.App(cfgmod.load())
    finally:
        del t.Widget.bind
    dbl = [fn for w, seq, fn in binds if seq == "<Double-Button-1>" and w in (app.f_header, app.f_logo)]
    assert len(dbl) == 2, dbl                            # a double click on the header (or its empty logo) toggles too
    shown = {}
    parts = {"tabs": app.f_tabs, "body": app.f_scrollbox, "status": app.f_status, "foot": app.f_foot}
    for name, w in parts.items():
        w.pack = lambda *a, n=name, **k: shown.__setitem__(n, True)
        w.pack_forget = lambda n=name: shown.__setitem__(n, False)
    app.v_model.set("qwen")
    app._apply_start_state()
    assert shown["tabs"] and shown["body"], shown
    app.toggle_minimize()
    assert app._minimized and not any(shown.values()), shown
    assert app.tt_min.text.startswith("Show the plugin")
    app._apply_start_state()                             # a refresh while minimised packs nothing again
    assert not any(shown.values()), shown
    app.toggle_minimize()
    assert not app._minimized and all(shown.values()), shown
    assert app.tt_min.text.startswith("Minimise")
    dbl[0](None)                                         # double click: minimised, again: back
    assert app._minimized and not any(shown.values()), shown
    dbl[1](None)
    assert not app._minimized and all(shown.values()), shown
    print("test_header_minimize: ok")


if __name__ == "__main__":
    main()
