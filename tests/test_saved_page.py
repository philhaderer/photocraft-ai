"""Right-click on a model chip: "Set as my settings for this mode and model" (user 30.10., renamed 31.10.; "Load default settings" was dropped).
The saved settings (not the prompt, the seed or the page itself) are the starting settings of that model and function:
they come back when the page opens and with "Reset page". Stubbed Tk.

    python tests/test_saved_page.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
models = gui.models


def main():
    # the config file
    assert cfgmod.saved_page("fibo", "inpaint") == {}
    cfgmod.set_saved_page("fibo", "inpaint", {"steps": 9})
    assert cfgmod.saved_page("fibo", "inpaint") == {"steps": 9} and cfgmod.saved_page("fibo", "edit") == {}
    cfgmod.set_saved_page("fibo", "inpaint", None)
    assert cfgmod.saved_page("fibo", "inpaint") == {} and cfgmod.get_setting("saved_pages") is None

    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    for rb in app.rb_modes.values():
        rb.grid = lambda *a, **k: None
    app.v_model.set("fibo")
    app.v_mode.set("inpaint")
    app._on_model()
    factory = (app.v_feather.get(), app.v_context.get())

    # change things, save: prompt, seed and the page are not part of it
    app.v_feather.set(9.5)
    app.v_context.set(0.7)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red flower")
    app.v_seed.set(77)
    app._save_page("fibo")
    s = cfgmod.saved_page("fibo", "inpaint")
    assert s["feather_pct"] == 9.5 and abs(s["context"] - 0.7) < 1e-9
    assert not {"prompt", "negative", "seed", "mode", "workflow", "clip", "checkpoint"} & set(s), sorted(s)
    assert "Saved my settings" in app.v_status.get()

    # another function and back: the saved settings are the start values of the page
    app.v_mode.set("edit")
    app._apply_model_mode()
    app.v_feather.set(2.0)                  # something else on the other page
    app.v_mode.set("inpaint")
    app._apply_model_mode()
    assert app.v_feather.get() == 9.5 and abs(app.v_context.get() - 0.7) < 1e-9
    # Reset page brings the saved ones back, not the factory ones
    app.v_feather.set(1.0)
    app.reset_settings()
    assert app.v_feather.get() == 9.5
    # another model's page is not touched
    assert cfgmod.saved_page("qwen", "inpaint") == {}

    print("ALL OK (saved page)")


if __name__ == "__main__":
    main()
