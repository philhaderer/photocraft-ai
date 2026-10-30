"""Reset brings back everything a fresh start of the same tab and function has (stubbed Tk).

Every setting in the window is changed, then Reset; the result must equal a new window opened on that tab. Kept on
purpose: the panels you opened (Advanced, negative prompt), the checkpoint file of the built-in graph and the
always-on-top flag (no switch). Also: a function's Context does not depend on the tab shown before (Fibo Fill showed
0.4 after Qwen and 0.2 after Reset).

    python tests/test_reset_all.py
"""
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
from pccomfy import models  # noqa: E402

gui, cfgmod = t.gui, t.cfgmod
KEPT = {"v_neg_open", "v_adv_open", "v_ckpt", "v_top"}
SHOWN = {"v_conn", "v_status", "v_pl", "v_pl_rest", "v_empty", "v_model", "v_mode", "v_workflow",
         "v_chip_fav"}   # display only / the tab (v_chip_fav: the tick in the right-click menu of a model chip)


def make():
    cfgmod.STATE_FILE.unlink(missing_ok=True)   # a new window as on the very first start, no remembered values
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    return app


def go(app, model, mode):
    app.v_model.set(model)
    app.v_mode.set(mode)
    app._on_model()


def snapshot(app):
    out = {k: v.get() for k, v in vars(app).items() if k.startswith("v_") and hasattr(v, "get") and k not in SHOWN | KEPT}
    out["t_prompt"] = app.t_prompt.get("1.0", "end").strip()
    out["t_neg"] = app.t_neg.get("1.0", "end").strip()
    out["stages"] = [v.get() for v in app.stage_vars]
    out["loras"] = list(app._loras())
    return out


def scramble(app):
    for k, v in vars(app).items():
        if k.startswith("v_") and hasattr(v, "get") and k not in SHOWN:
            cur = v.get()
            if isinstance(cur, bool):
                v.set(not cur)
            elif isinstance(cur, int):
                v.set(cur + 3)
            elif isinstance(cur, float):
                v.set(round(cur + 0.13, 2))
            elif isinstance(cur, str):
                v.set(cur + "x" if cur else "x")
    app.t_neg.insert("1.0", "neg")
    for sv in app.stage_vars:
        sv.set(not sv.get())


def main():
    for m in models.MODELS:
        for mode in m.modes:
            fresh = make()
            go(fresh, m.key, mode)
            fresh._mode_denoise()       # a function chosen by hand also sets its Denoise (_on_mode)
            want = snapshot(fresh)
            app = make()
            go(app, m.key, mode)
            scramble(app)
            app.reset_settings()
            got = snapshot(app)
            diff = {k: (want.get(k), got.get(k)) for k in set(want) | set(got) if want.get(k) != got.get(k)}
            assert not diff, (m.key, mode, diff)

    # the Context a function starts with does not come from the tab before
    # (Fibo Fill has its own 0.4 since the test round 28.10.; Fill without one starts at FILL_CONTEXT)
    fibo_fill = models.BY_KEY["fibo"].modes["inpaint"].settings["context"]
    for before in ("qwen", "flux3"):
        app = make()
        go(app, before, "inpaint" if "inpaint" in models.BY_KEY[before].modes else "edit")
        app.v_context.set(0.9)
        go(app, "fibo", "inpaint")
        assert app.v_context.get() == fibo_fill, (before, app.v_context.get())
    app = make()
    go(app, "fibo", "inpaint")
    app.v_context.set(0.9)
    app.reset_settings()
    assert app.v_context.get() == fibo_fill
    go(app, "qwen", "inpaint")
    app.v_context.set(0.9)
    app.reset_settings()
    assert app.v_context.get() == 0.4       # Qwen Fill's own start value
    # Context is a slider from 0 to 1 in steps of 0.05 (shown as 0 to 100 %); its box follows every change (Reset, a tab change)
    assert isinstance(app.w_adv["Context"], gui.Slider)
    app.v_context.set(0.33)
    app._on_context()
    assert app.v_context.get() == 0.35 and app.lbl_context.cget("text") == "35 %"
    app.reset_settings()
    assert app.lbl_context.cget("text") == "40 %"
    app.v_context.set(0.75)
    app._on_context()
    go(app, "fibo", "inpaint")
    assert app.lbl_context.cget("text") == "40 %"
    app.v_context.set(1.6)                     # an old saved value beyond the slider
    assert app._request().context == 1.0
    # Defaults also works while a run is on (user 30.10.); Generate and Variants stay grey until the run is done
    app = make()
    go(app, "qwen", "inpaint")
    app.v_context.set(0.9)
    app.v_seed.set(123)
    app.worker = threading.Thread(target=lambda: None)
    app.worker.is_alive = lambda: True
    app._running = True                        # as generate() sets it
    app.b_go.configure(state="disabled")
    app.w_variants.configure(state="disabled")
    app.reset_settings()
    assert app.v_context.get() == 0.4 and app.v_seed.get() == -1
    assert app.b_go["state"] == "disabled" and app.w_variants["state"] == "disabled"
    go(app, "fibo", "inpaint")                 # a tab change during the run keeps it grey too
    assert app.w_variants["state"] == "disabled"
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ok")


if __name__ == "__main__":
    main()
