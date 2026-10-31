"""Easy Mode in the real Tk window (hidden): the switch hides the model chips, the negative prompt and everything between the
prompt and the status line; the plugin picks the model per function; switching off brings the normal window back exactly.
Skipped when Tk cannot open a window.

    python tests/test_easymode_gui.py
"""
import os
import shutil
import threading
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="pccomfy-easygui-")
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
from pccomfy import easymode as em  # noqa: E402
from pccomfy import gui, models  # noqa: E402


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
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red kite")
    app.v_seed.set(1234)
    app.root.update()
    assert not app._easy and shown(app.f_models) and shown(app.f_neg) and shown(app.f_adv) and shown(app.b_reset)
    before = list(app.f_body.pack_slaves())
    before_all = {k: shown(getattr(app, k)) for k in ("f_models", "f_neg", "f_enh", "f_adv", "b_llm", "b_reset", "f_opts")}

    # a page the user saved is ignored in Easy Mode
    cfgmod.set_setting("saved_pages", {"fibo|inpaint": {"steps": 7}})

    app.v_easy.set(True)
    app.toggle_easy()
    app.root.update()
    assert app._easy and em.is_on()
    assert app.v_mode.get() == "inpaint" and app.v_model.get() == "fibo", (app.v_mode.get(), app.v_model.get())
    assert app.v_steps.get() != 7
    assert app.v_seed.get() == -1
    for w in (app.f_models, app.f_neg, app.f_enh, app.f_adv, app.f_opts, app.b_llm, app.b_reset, app.f_pchoice):
        assert not shown(w), w
    assert shown(app.lbl_easy_model) and app.v_easy_model.get() == models.BY_KEY["fibo"].label
    assert shown(app.f_go) and shown(app.t_prompt) and shown(app.cb_live) and shown(app.b_history) and shown(app.b_copy_canvas)
    assert shown(app.b_easy)
    on = [k for k, rb in app.rb_modes.items() if shown(rb)]
    assert on == [k for k, _ in gui.MODE_LABELS if k in em.EASY_MODES], on                       # no Multi Image Edit, no Refine
    assert app.t_prompt.get("1.0", "end").strip() == "a red kite"

    # a function click picks the best model for it
    for mode, want in (("txt2img", "flux3"), ("edit", "flux3"), ("remove", "fibo"), ("outpaint", "flux2"), ("upscale", "flux3")):
        app.v_mode.set(mode)
        app._on_mode()
        app.root.update()
        assert app.v_model.get() == want, (mode, app.v_model.get())
        assert app.v_easy_model.get() == models.BY_KEY[want].label
        assert not shown(app.f_neg) and not shown(app.f_adv) and not shown(app.f_models) and not shown(app.f_opts)
    assert shown(app.f_scale)                                  # Upscale factor stays in Upscale
    app.v_mode.set("edit")
    app._on_mode()
    assert not shown(app.f_scale)

    # no model for a function: its button is greyed out; the current function moves to one that has a model
    app.v_mode.set("upscale")
    app._on_mode()
    app._model_usable = lambda key, mode: key == "fibo"
    app._easy_refresh()
    app.root.update()
    assert str(app.rb_modes["upscale"].cget("state")) == "disabled"
    assert str(app.rb_modes["edit"].cget("state")) == "normal"
    assert app.v_model.get() == "fibo" and app.v_mode.get() == "txt2img", (app.v_model.get(), app.v_mode.get())
    assert app.tt_modes["upscale"].text == em.MODE_GREYED_TIP
    del app._model_usable

    # back to the normal window: the same stacking order, the same model, function, settings
    app.v_mode.set("upscale")
    app._on_mode()
    app.v_easy.set(False)
    app.toggle_easy()
    app.root.update()
    assert not app._easy and not em.is_on() and em.pop_return() == {}
    assert app.v_model.get() == "qwen" and app.v_mode.get() == "inpaint", (app.v_model.get(), app.v_mode.get())
    assert app.v_seed.get() == 1234
    assert app.t_prompt.get("1.0", "end").strip() == "a red kite"
    assert {k: shown(getattr(app, k)) for k in before_all} == before_all
    assert list(app.f_body.pack_slaves()) == before, "stacking order changed"
    assert not shown(app.lbl_easy_model)
    assert all(shown(rb) for rb in app.rb_modes.values() if rb is not app.rb_modes.get("img2img"))

    # the settings window has a tab "Easy Mode" between "Models" and "Credits" with the button for the starter models
    from pccomfy import inventory, manifest
    calls = []
    app.download_missing = lambda key, required_only=False: calls.append((tuple(key), required_only))
    app.inv = inventory.Inventory({k: [] for k in inventory.LIST_KINDS}, None, None)      # ComfyUI lists nothing
    app.open_settings()
    app.root.update()
    tabs = [app.nb_settings.tab(i, "text") for i in range(app.nb_settings.index("end"))]
    assert tabs == ["Models", em.TAB_TITLE, "Credits"], tabs

    def texts(w):
        out = []
        for c in w.winfo_children():
            if c.winfo_class() in ("TLabel", "TButton"):
                out.append(str(c.cget("text")))
            out += texts(c)
        return out
    t = texts(app._easy_tab)
    assert em.TAB_MORE in t and not any("(best)" in x or x.startswith("Multi Image Edit:") for x in t), t      # no ranking in the tab
    assert t.index(next(x for x in t if x.startswith(em.TAB_BUTTON))) < t.index(em.TAB_FLUX3_NOTE), t         # the button comes first
    assert em.TAB_INFO in t and any(x.startswith(em.TAB_BUTTON) for x in t) and em.TAB_FLUX3_NOTE in t, t
    need = {f.name for f in app._starter_missing()}
    assert need and all(name in need for name in manifest.tab_required("fibo")) and all(name in need for name in manifest.tab_required("flux3"))
    assert any(name in x for x in t for name in need)         # the missing files are listed
    btn = next(c for c in app._easy_tab.winfo_children()[0].winfo_children() if c.winfo_class() == "TButton")
    btn.invoke()
    assert calls == [(em.STARTER_MODELS, True)], calls
    # a running download shows a bar, the percent and a cross in the tab
    name = sorted(need)[0]
    f0 = manifest.FILES[name]
    app._dl[name] = {"file": f0, "target": None, "done": f0.size // 2, "total": f0.size, "phase": "downloading", "cancel": threading.Event()}
    app._easy_tab_draw()
    app.root.update()
    w = app._dl_widgets_easy[name]
    assert w["label"].cget("text") == "50 %", w["label"].cget("text")
    assert str(next(c for c in app._easy_tab.winfo_children()[0].winfo_children() if c.winfo_class() == "TButton").cget("state")) == "disabled"
    app._dl.clear()
    app.inv = None
    app._easy_tab_draw()
    assert any("could not be read" in x for x in texts(app._easy_tab))
    app._settings_close()

    # Easy Mode left on is on again at the next start
    em.set_on(True)
    app.root.destroy()
    app2 = gui.App(cfg)
    app2.root.withdraw()
    app2.root.update()
    assert app2._easy and not shown(app2.f_neg) and not shown(app2.f_models) and not shown(app2.f_adv)
    app2.root.destroy()
    shutil.rmtree(TMP, ignore_errors=True)
    print("ALL OK (easy mode window)")


if __name__ == "__main__":
    main()
