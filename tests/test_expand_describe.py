"""Krea 2 / MOSS Expand need a prompt (user 29.10., A/B test docs/tests/krea-moss-expand-ab.md): their own tip under the
field, a Describe button under it that writes a description of the surroundings (Qwen 3.5 9B, SCENE_QUESTION) into the
field, and Generate refuses an empty prompt with a message. Other models' Expand stays as it was. Since the blind test
of 29.10. both modes are parked (models.PARKED_EXPAND, not offered); the test puts them back for its duration, so the
button keeps working for when they return. Stubbed Tk, PhotoCraft and ComfyUI.

    python tests/test_expand_describe.py
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
import test_reference_mode as t  # noqa: E402

from pccomfy import bridge, imaging, models  # noqa: E402


def model_checks():
    assert "outpaint" not in models.BY_KEY["krea2"].modes                # parked (off since 29.10.)
    spec = models.PARKED_EXPAND["krea2"]
    assert spec.describe and spec.prompt_tip == models.EXPAND_DESCRIBE_TIP
    assert "moss" not in models.PARKED_EXPAND                             # MOSS Expand is back since 1.11. (Inpainting v10), still with Describe
    moss = models.BY_KEY["moss"].modes["outpaint"]
    assert moss.describe and moss.prompt_tip == models.EXPAND_DESCRIBE_TIP
    for m in models.MODELS:
        if m.key not in ("krea2", "moss") and "outpaint" in m.modes:
            assert not m.modes["outpaint"].describe and not m.modes["outpaint"].prompt_tip, m.key


def bridge_checks():
    # the original lies inside an extended, transparent canvas: only it is described, with the question about the surroundings
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, layers=1)
    asked = []
    b.describe_image = lambda im, progress=None, question="", **kw: asked.append((im.size, question)) or "a quiet forest"
    assert b.describe_scene() == "a quiet forest"
    (size, question), = asked
    src = t.rect(t.YELLOW, (140, 20, 180, 80))
    keep = imaging.content_box(src)
    assert keep is not None and size == (keep.w, keep.h), (size, keep)
    assert question == bridge.SCENE_QUESTION and "main subject" in question
    # no empty margin (the last Expand filled it): the place of that Expand, same canvas size
    pc2, _, b2 = t.make(tempfile.mkdtemp(), layers=3)
    b2._last_expand = {"doc": "scene.png", "size": (t.W, t.H), "keep": imaging.Box(10, 10, 50, 40), "layers": []}
    asked.clear()
    b2.describe_image = lambda im, progress=None, question="", **kw: asked.append(im.size) or "x"
    b2.describe_scene()
    assert asked == [(50, 40)], asked


def gui_checks():
    app = ra.make()
    packed = {}
    app.b_describe.pack = lambda *a, **k: packed.__setitem__("b", True)
    app.b_describe.pack_forget = lambda: packed.__setitem__("b", False)
    for key in ("krea2", "moss"):
        ra.go(app, key, "outpaint")
        assert app._hint_text == models.EXPAND_DESCRIBE_TIP and packed["b"] is True, key
        # empty prompt: no run, a message that says what to do
        app.t_prompt.delete("1.0", "end")
        called = []
        app._request = lambda: called.append(1) or (_ for _ in ()).throw(ValueError("stop"))
        app.generate()
        assert called == [] and "Describe" in app.v_status.get(), app.v_status.get()
        # with a text it goes on (to _request)
        app.t_prompt.insert("1.0", "a quiet forest")
        app.generate()
        assert called == [1]
        del app._request
    for key in ("qwen", "flux2", "fibo"):
        ra.go(app, key, "outpaint")
        assert app._hint_text == ra.gui.EXPAND_HINT and packed["b"] is False, key
    ra.go(app, "krea2", "txt2img")
    assert packed["b"] is False
    # the button writes the description into the field (one undo step)
    ra.go(app, "moss", "outpaint")
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "old text")
    app.bridge.describe_scene = lambda: "a dim rustic room with wooden walls"
    pending = []
    app.root.after = lambda ms, fn=None, *a: pending.append(fn)
    app.describe_scene()
    for _ in range(50):
        if not pending:
            break
        time.sleep(0.02)
        pending.pop(0)()
    assert app.t_prompt.get("1.0", "end").strip() == "a dim rustic room with wooden walls"
    assert "Described" in app.v_status.get()
    # a failure is shown, the field stays
    app.bridge.describe_scene = lambda: (_ for _ in ()).throw(RuntimeError("ComfyUI is not running"))
    app.describe_scene()
    for _ in range(50):
        if not pending:
            break
        time.sleep(0.02)
        pending.pop(0)()
    assert "Describe failed" in app.v_status.get() and "wooden" in app.t_prompt.get("1.0", "end")


def main():
    model_checks()
    bridge_checks()
    for key, spec in models.PARKED_EXPAND.items():      # back for the window checks only
        models.BY_KEY[key].modes["outpaint"] = spec
    try:
        gui_checks()
    finally:
        for key in models.PARKED_EXPAND:
            models.BY_KEY[key].modes.pop("outpaint", None)
    print("ALL OK (expand describe)")


if __name__ == "__main__":
    main()
