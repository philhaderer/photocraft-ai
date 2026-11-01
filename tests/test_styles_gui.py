"""The Styles button in the real Tk window (hidden): it sits left of the LLM button only in Text to image, goes in Easy Mode and
comes back, the menu has a submenu per group, an entry REPLACES the prompt in one undo step (Ctrl+Z brings the old text back),
and the hover box shows the whole text. Skipped when Tk cannot open a window.

    python tests/test_styles_gui.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="pccomfy-stylesgui-")
os.environ["PCCOMFY_HOME"] = TMP
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    _r = tkinter.Tk()
    _r.destroy()
except Exception as e:                      # no display / no Tk
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui, models, styles  # noqa: E402


def shown(w) -> bool:
    return bool(w.winfo_manager())


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    app.v_model.set("flux3")
    app.v_mode.set("edit")
    app._on_model()
    app.root.update()
    assert not shown(app.b_styles)                                  # not in Edit Canvas
    app.v_mode.set("txt2img")
    app._on_model()
    app.root.update()
    assert shown(app.b_styles) and shown(app.b_llm)
    assert app.b_styles.winfo_x() < app.b_llm.winfo_x() < app.b_clear.winfo_x()

    # the menu: a submenu per group, an entry per style, names only
    top = app.m_styles["txt2img"]
    groups = styles.load()["txt2img"]
    assert top.index("end") == len(groups) - 1
    assert [top.entrycget(i, "label") for i in range(len(groups))] == [g["name"] for g in groups]
    sub = top.nametowidget(top.entrycget(0, "menu"))
    assert [sub.entrycget(i, "label") for i in range(len(groups[0]["styles"]))] == [s["name"] for s in groups[0]["styles"]]

    # an entry replaces the prompt; one Ctrl+Z brings the old text back
    app.t_prompt.configure(undo=True)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red bicycle")
    app.t_prompt.edit_reset()
    sub.invoke(2)
    want = groups[0]["styles"][2]["text"]
    assert app.t_prompt.get("1.0", "end").strip() == want
    app.t_prompt.edit_undo()
    assert app.t_prompt.get("1.0", "end").strip() == "a red bicycle", repr(app.t_prompt.get("1.0", "end"))

    # the hover box: shown for an active entry, gone for none and after a hide. (A real posted menu is a native Windows menu that
    # a test cannot drive reliably, so the active entry is faked: a menu that says entry 1 is active.)
    class Active:
        def __init__(self, real, active):
            self.real, self.active = real, active

        def __str__(self):
            return str(self.real)

        def index(self, what):
            return self.active

        def yposition(self, i):
            return 5

        def __getattr__(self, name):
            return getattr(self.real, name)
    app._style_preview(Active(sub, 1))
    assert app._style_tip is not None
    labels = [w for w in app._style_tip.winfo_children() if w.winfo_class() == "Label"]
    assert labels and labels[0].cget("text") == groups[0]["styles"][1]["text"]
    app._style_tip_hide()
    assert app._style_tip is None
    app._style_preview(Active(sub, "none"))
    assert app._style_tip is None

    # Easy Mode hides the button (like the LLM button) and shows it again, still left of LLM
    app.v_easy.set(True)
    app.toggle_easy()
    app.root.update()
    assert not shown(app.b_styles) and not shown(app.b_llm)
    app.v_easy.set(False)
    app.toggle_easy()
    app.root.update()
    assert shown(app.b_styles) and app.b_styles.winfo_x() < app.b_llm.winfo_x() < app.b_clear.winfo_x()
    app.root.destroy()
    print("ALL OK (styles gui)")


if __name__ == "__main__":
    main()
