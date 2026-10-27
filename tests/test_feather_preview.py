"""Feather preview: the soft edge the next run would get, shown as Quick Mask in PhotoCraft, and the user's selection back.

Against the PhotoCraft simulator (behaviour measured in 0.15.1 and 0.16: Quick Mask on = no selection reported, the
copy of the helper layer makes the destination active); the window's button against the Tk stub.

    python tests/test_feather_preview.py
"""
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import imaging, workflows  # noqa: E402
from pccomfy.bridge import BridgeError, Request, soft_layer_mask  # noqa: E402

WF = ROOT / "workflows"


def req(wf="fibo2-edit.json", layer_mask="soft", feather=10.0):
    r = Request(mode="inpaint", workflow=str(WF / wf), layer_mask=layer_mask, feather_pct=feather, context=0.4, enhance=False)
    r.params = workflows.GenParams(prompt="a red ball", seed=3)
    return r


def expected(sel: Image.Image, r: Request, shape: str = "soft") -> np.ndarray:
    bbox = imaging.mask_bbox(sel)
    region = imaging.grow_box(bbox, sel.size, r.context)
    if shape == "soft":
        m = soft_layer_mask(r, workflows.resolve(r.workflow), sel, region, bbox)
    elif shape == "hard":
        m = sel.crop(region.pil())
    else:
        m = Image.new("L", (region.w, region.h), 255)
    out = np.zeros((sel.size[1], sel.size[0]), np.uint8)
    out[region.y:region.y + region.h, region.x:region.x + region.w] = np.asarray(m)
    return out


def bridge_checks():
    pc, _, b = T.make(tempfile.mkdtemp())
    d = pc.docs[0]
    d.active = 2            # PhotoCraft always has an active layer: it must stay the active one
    sel0 = d.sel.copy()
    ids0, act0 = [l["id"] for l in d.layers], d.active

    # show: Quick Mask on with exactly the run's soft mask; the user's selection saved; no layer left behind
    msg = b.show_feather(req(feather=10.0))
    assert "Soft edge" in msg and b.feather_shown
    assert d.quick is not None and d.sel is None
    assert np.array_equal(np.asarray(d.quick), expected(sel0, req(feather=10.0)))
    assert len(d.channels) == 1 and [l["id"] for l in d.layers] == ids0 and d.active == act0 and len(pc.docs) == 1
    soft10 = np.asarray(d.quick).copy()

    # the slider moved: shown anew without a second export of the picture
    n_dup = sum(1 for c, _ in pc.log if c == "image.duplicate")
    b.show_feather(req(feather=3.0))
    assert sum(1 for c, _ in pc.log if c == "image.duplicate") == n_dup
    assert np.array_equal(np.asarray(d.quick), expected(sel0, req(feather=3.0))) and not np.array_equal(np.asarray(d.quick), soft10)
    assert len(d.channels) == 1

    # hide: the user's own selection back, Quick Mask off, the channel gone
    assert "selection is back" in b.hide_feather()
    assert not b.feather_shown and d.quick is None and not d.channels
    assert np.array_equal(np.asarray(d.sel), np.asarray(sel0)) and [l["id"] for l in d.layers] == ids0
    assert b.hide_feather() == ""     # nothing shown: nothing to do

    # the hard layer mask shows the selection itself, "none" the whole rectangle the result covers
    for lm, shape in (("selection", "hard"), ("none", "none")):
        b.show_feather(req(layer_mask=lm))
        assert np.array_equal(np.asarray(d.quick), expected(sel0, req(layer_mask=lm), shape)), lm
        b.hide_feather()
    # a mask-using workflow (Krea Fill): the grown and blurred mask the model gets
    b.show_feather(req("krea2-turbo-inpaint.json", "auto"))
    assert np.array_equal(np.asarray(d.quick), expected(sel0, req("krea2-turbo-inpaint.json", "auto")))
    b.hide_feather()

    # Generate while it is shown: the run brings the selection back first and works on it
    b.show_feather(req())
    b.comfy = T.FakeComfy()
    res = b.run(req())
    assert res["layers"] and not b.feather_shown and d.quick is None and not d.channels
    assert np.array_equal(np.asarray(d.sel), np.asarray(sel0))
    sent = b.comfy.uploads
    assert any(k.endswith("-image.png") for k in sent)

    # no selection: a clear message, nothing changed
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    try:
        b.show_feather(req())
        raise AssertionError("expected an error without a selection")
    except BridgeError as e:
        assert "Select an area first" in str(e)
    assert not b.feather_shown and not pc.docs[0].channels and pc.docs[0].quick is None

    # another document is active when it ends: its selection comes back in its own document, the active one stays
    pc, _, b = T.make(tempfile.mkdtemp())
    sel0 = pc.docs[0].sel.copy()
    b.show_feather(req())
    pc.docs.append(T.Doc("other.png", [{"id": 999, "img": Image.new("RGBA", (T.W, T.H)), "visible": True}]))
    pc.active = 1
    b.hide_feather()
    assert pc.active == 1 and np.array_equal(np.asarray(pc.docs[0].sel), np.asarray(sel0)) and pc.docs[0].quick is None

    # it breaks off half way: never a lost selection
    pc, _, b = T.make(tempfile.mkdtemp())
    sel0 = pc.docs[0].sel.copy()
    real = pc.execute
    def broken(cmd, params=None):
        if cmd == "select.editInQuickMaskMode" and params.get("on"):
            from pccomfy.photocraft import PhotoCraftError
            raise PhotoCraftError("select.editInQuickMaskMode: test failure")
        return real(cmd, params)
    pc.execute = broken
    try:
        b.show_feather(req())
    except Exception as e:
        assert "test failure" in str(e), e
    assert not b.feather_shown and not pc.docs[0].channels and np.array_equal(np.asarray(pc.docs[0].sel), np.asarray(sel0))


class StubBridge:
    """Only what the window's button uses."""
    def __init__(self):
        self.feather_shown, self.calls = False, []

    def show_feather(self, req):
        self.calls.append(("show", req.feather_pct))
        self.feather_shown = True
        return "Soft edge shown"

    def hide_feather(self):
        self.calls.append(("hide",))
        self.feather_shown = False
        return "Feather preview off: your selection is back."


def gui_checks():
    import test_gui_presets as t   # installs the Tk stub and a temporary PCCOMFY_HOME
    gui, cfgmod = t.gui, t.cfgmod
    app = gui.App(cfgmod.load())
    app.bridge = StubBridge()

    def settle():
        if app.worker:
            app.worker.join(5)
        while not app.events.empty():
            kind, data = app.events.get_nowait()
            if kind == "feather":
                app._feather_done(*data)

    assert app.b_fprev["text"] == "Show feather"
    app.v_workflow.set(gui.BUILTIN)
    app.v_mode.set("inpaint")
    app.toggle_feather_preview()
    settle()
    assert app.bridge.calls[-1][0] == "show" and app._fprev_on and app.b_fprev["text"] == "Hide feather"
    app.toggle_feather_preview()
    settle()
    assert app.bridge.calls[-1] == ("hide",) and not app._fprev_on and app.b_fprev["text"] == "Show feather"
    # switching to a function without an edge feather ends a shown preview
    app.toggle_feather_preview()
    settle()
    app.v_mode.set("outpaint")
    app._update_feather_state()
    settle()
    assert app.bridge.calls[-1] == ("hide",) and app.b_fprev["text"] == "Show feather"
    # a click while the worker is busy with something else does nothing
    app.v_mode.set("inpaint")
    app._update_feather_state()
    app.worker = threading.Thread(target=lambda: None)
    app.worker.is_alive = lambda: True
    n = len(app.bridge.calls)
    app.toggle_feather_preview()
    assert len(app.bridge.calls) == n
    app.worker = None


def main():
    bridge_checks()
    gui_checks()
    print("ok")


if __name__ == "__main__":
    main()
