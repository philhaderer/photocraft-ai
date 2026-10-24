"""Edge feather is greyed out whenever no soft layer mask is used (stubbed Tk, no display needed).

    python tests/test_feather_state.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
L = gui.LAYER_MASKS


def main():
    app = gui.App(cfgmod.load())
    Path(app.workflows_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(t.ROOT / "workflows" / "fibo2-edit-plain.json", Path(app.workflows_dir) / "fibo2-edit-plain.json")
    app.cb_workflow["values"] = [gui.BUILTIN, "fibo2-edit-plain.json"]

    def state(wf, mode, choice):
        app.v_workflow.set(wf)
        app.v_mode.set(mode)
        app.v_lmask.set(L[choice])
        app._update_feather_state()
        return app.w_feather["state"]

    # auto: off for Fill with a Fibo-type editor, on for Expand and for the built-in graph
    assert state("fibo2-edit-plain.json", "inpaint", "auto") == "disabled"
    assert state("fibo2-edit-plain.json", "outpaint", "auto") == "normal"
    assert state(gui.BUILTIN, "inpaint", "auto") == "normal"
    # explicit choices: only "soft" uses the feather
    assert state("fibo2-edit-plain.json", "inpaint", "soft") == "normal"
    assert state("fibo2-edit-plain.json", "inpaint", "selection") == "disabled"
    assert state("fibo2-edit-plain.json", "outpaint", "none") == "disabled"
    # changing the mode / the layer mask choice / loading a preset refreshes it by itself
    app.v_workflow.set("fibo2-edit-plain.json")
    app.v_lmask.set(L["auto"])
    app.v_mode.set("inpaint")
    app._on_mode_ui()
    assert app.w_feather["state"] == "disabled"
    app.v_mode.set("outpaint")
    app._on_mode_ui()
    assert app.w_feather["state"] == "normal"
    app.v_mode.set("inpaint")
    app._apply_settings({"mode": "inpaint", "layer_mask": "soft"})
    assert app.w_feather["state"] == "normal"
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (feather state)")


if __name__ == "__main__":
    main()
