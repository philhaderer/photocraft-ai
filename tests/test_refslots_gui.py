"""Multi Image Edit in the window (stubbed Tk): the slots show only where the model has them, Ctrl+V / Paste / files fill them,
the request carries the images.

    python tests/test_refslots_gui.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
from PIL import Image  # noqa: E402

gui, cfgmod = t.gui, t.cfgmod
from pccomfy import clipboard, refslots  # noqa: E402


def main():
    import shutil
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in gui.models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    log = []

    def pick(model, mode):
        app.v_model.set(model)
        app.v_mode.set(mode)
        app._on_model()

    pick("moss", "txt2img")
    assert getattr(app, "f_refs", None) is None, "a model without slots builds nothing"
    assert app._request().refs == []

    pick("qwen", "multi_edit")
    assert app.f_refs is not None
    app.f_refs.pack = lambda *a, **k: log.append("on")
    app.f_refs.pack_forget = lambda: log.append("off")
    pick("qwen", "inpaint")
    assert log[-1] == "off"                                  # the slots belong to Multi Image Edit only
    pick("qwen", "edit")
    assert log[-1] == "off"
    pick("qwen", "multi_edit")
    assert log[-1] == "on" and app.refslots.max_refs == 2 and app.refslots.tag_style == "<image{n}>"
    pick("qwen", "remove")
    assert log[-1] == "off"                                  # Remove Selection takes no references
    pick("qwen", "multi_edit")
    assert log[-1] == "on"

    # Paste button / Ctrl+V
    img = Image.new("RGB", (40, 30), "red")
    orig = clipboard.read_image
    try:
        clipboard.read_image = lambda hwnd=0: None
        app._refs_paste()
        assert not app.refslots.items and ("no picture" in app.lbl_refmsg["text"] or "Windows" in app.lbl_refmsg["text"])
        clipboard.read_image = lambda hwnd=0: img
        app._refs_paste()
        assert len(app.refslots.items) == 1 and app.lbl_refnames["text"].startswith("Name them in your text: picture = <image1>")
        assert app._refs_ctrl_v() == "break" and len(app.refslots.items) == 2
        assert app._refs_ctrl_v() == "break" and len(app.refslots.items) == 2 and "full" in app.lbl_refmsg["text"]   # the third does not fit
        # a text field keeps Ctrl+V
        class Focus:
            def winfo_class(self):
                return "Text"
        app.root.focus_get = lambda: Focus()
        before = len(app.refslots.items)
        app.refslots.remove(0)
        assert app._refs_ctrl_v() is None and len(app.refslots.items) == before - 1
        app.root.focus_get = lambda: None
    finally:
        clipboard.read_image = orig

    # dropped files (names with spaces arrive in braces)
    tmp = Path(tempfile.mkdtemp())
    Image.new("RGB", (20, 20), "blue").save(tmp / "a b.png")
    (tmp / "x.txt").write_text("no")
    app.refslots.clear()
    app._refs_on_drop(type("E", (), {"data": "{%s} %s" % (tmp / "a b.png", tmp / "x.txt"), "action": "copy"})())
    assert [it.name for it in app.refslots.items] == ["a b.png"] and "not a picture" in app.lbl_refmsg["text"]

    assert app.ICON_SCALE == 1.7 and app._icon_px() == 27 and app._bar_px() == 33      # icons 70 % bigger, one constant
    # the icon bars: paste and add file in the next free slot, five icons in a filled slot (copy text only with a description)
    app.refslots.clear()
    app._ref_icon_cache.clear()
    app._refs_redraw()
    kinds = {k for k, _c in app._ref_icon_cache}
    assert {"paste", "file"} <= kinds and "remove" not in kinds
    app.refslots.add(img, "q.png")
    app._ref_icon_cache.clear()
    app._refs_redraw()
    kinds = {k for k, _c in app._ref_icon_cache}
    assert {"remove", "cut", "describe"} <= kinds and "pen" not in kinds and "copy" not in kinds
    app.refslots.items[0].description = "A red square."
    app._refs_redraw()
    assert "copy" in {k for k, _c in app._ref_icon_cache}
    copied = []
    app.root.clipboard_clear = lambda: copied.clear()
    app.root.clipboard_append = lambda t: copied.append(t)
    app._refs_copy_text(0)
    assert copied == ["A red square."]
    app.refslots.clear()
    app.refslots.add(img, "a b.png")

    # the request: the images go along in Edit / Fill / Expand, never in other modes or for a model without slots
    app.refslots.add(img, "r.png")
    req = app._request()
    assert req.mode == "edit" and len(req.refs) == 2
    pick("flux2", "multi_edit")
    assert app.refslots.max_refs == 3 and len(app._request().refs) == 2 and app.refslots.tag(0) == "image 2"
    pick("flux2", "upscale")
    assert app._request().refs == []
    pick("qwen", "multi_edit")
    pick("moss", "txt2img")
    assert app._request().refs == [] and log[-1] == "off"
    pick("qwen", "multi_edit")
    assert len(app._request().refs) == min(2, len(app.refslots.items))      # nothing was lost by the tab switch

    # the cut-out button: ComfyUI's answer replaces the picture, "Undo cut" brings the original back
    app.bridge.remove_background = lambda im: Image.new("RGBA", im.size, (0, 0, 0, 0))
    pending = []
    app.root.after = lambda ms, fn=None, *a: pending.append(fn) if getattr(fn, '__name__', '') == 'check' else None   # only the cut-out's own polling
    app._refs_cut(0)
    import time
    for _ in range(100):
        if app.refslots.items[0].cut_out or (pending and not app._ref_busy):
            break
        while pending:
            pending.pop(0)()
        time.sleep(0.02)
    while pending:
        pending.pop(0)()
    assert app.refslots.items[0].cut_out and not app._ref_busy
    app._refs_cut(0)
    assert not app.refslots.items[0].cut_out

    # the describe button: Qwen 3.5 9B's text lands in the slot and, on request, in the prompt (named like the model names the image)
    app.bridge.describe_image = lambda im: "A red square on blue."
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "put it on the sofa")
    app._refs_describe(0)
    for _ in range(100):
        while pending:
            pending.pop(0)()
        if app.refslots.items[0].description:
            break
        time.sleep(0.02)
    assert app.refslots.items[0].description == "A red square on blue." and not app._ref_busy
    assert app.lbl_refmsg["text"] == "<image2>: A red square on blue."
    assert app.t_prompt.get("1.0", "end").strip() == "put it on the sofa"          # the text field itself stays as typed
    assert app._request().params.prompt == "put it on the sofa\n<image2>: A red square on blue."   # the description goes along at the end
    assert not hasattr(app, "b_refuse")
    app.bridge.describe_image = lambda im: (_ for _ in ()).throw(RuntimeError("ComfyUI is not running"))
    app._refs_describe(0)
    for _ in range(100):
        while pending:
            pending.pop(0)()
        if "failed" in app.lbl_refmsg["text"]:
            break
        time.sleep(0.02)
    assert app.lbl_refmsg["text"] == "Describe failed: ComfyUI is not running" and not app._ref_busy

    assert not hasattr(refslots, "apply_strokes") and not hasattr(app, "_refs_pen")      # the pen is gone
    assert refslots.thumbnail_png(Image.new("RGBA", (300, 100), (0, 0, 0, 0)), 64)[:4] == b"\x89PNG"
    print("ALL OK (refslots gui)")


if __name__ == "__main__":
    main()
