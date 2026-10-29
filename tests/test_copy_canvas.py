"""Copy canvas to clipboard (L3, header button, user 29.10. option A): the visible layers of the active picture as one
image, through the export a run makes; hidden layers stay out, the document is left as it was. The window's button
against the Tk stub with a fake clipboard.

    python tests/test_copy_canvas.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy.bridge import BridgeError  # noqa: E402


def bridge_checks():
    pc, _, b = T.make(tempfile.mkdtemp())
    d = pc.docs[0]
    ids0, sel0 = [l["id"] for l in d.layers], d.sel.copy()
    img = b.canvas_image()
    assert img.size == (T.W, T.H) and T.has_yellow(img)                     # the top layer is in it
    assert [l["id"] for l in d.layers] == ids0 and len(pc.docs) == 1           # the duplicate is gone, nothing changed
    assert np.array_equal(np.asarray(d.sel), np.asarray(sel0))                # the selection stays

    d.layers[-1]["visible"] = False                                           # a hidden layer is not copied
    assert not T.has_yellow(b.canvas_image())

    pc.docs.clear()
    pc.active = None                                                          # (PhotoCraft without a document)
    try:
        b.canvas_image()
        raise AssertionError("no document must raise")
    except BridgeError as e:
        assert "Open a document" in str(e)


def gui_checks():
    import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
    gui = t.gui
    app = gui.App(t.cfgmod.load())
    put = []
    gui.clipboard.write_image = lambda img, **k: put.append(img) or True

    class B:
        def canvas_image(self):
            return "picture"
    app.bridge = B()
    app.copy_canvas()
    app.worker.join(5)
    assert put == ["picture"]
    assert app.events.get_nowait() == ("note", "Canvas copied to the clipboard.")

    class Bad:
        def canvas_image(self):
            raise BridgeError("Open a document in PhotoCraft first.")
    app.bridge = Bad()
    app.copy_canvas()
    app.worker.join(5)
    kind, msg = app.events.get_nowait()
    assert kind == "note-error" and msg == "Error: Open a document in PhotoCraft first.", (kind, msg)

    gui.clipboard.write_image = lambda img, **k: False
    app.bridge = B()
    app.copy_canvas()
    app.worker.join(5)
    assert app.events.get_nowait()[0] == "note-error"


def main():
    bridge_checks()
    gui_checks()
    print("test_copy_canvas: ok")


if __name__ == "__main__":
    main()
