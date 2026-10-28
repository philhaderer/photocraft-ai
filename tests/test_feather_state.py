"""Edge feather is greyed out whenever no soft layer mask is used, and for Fill with Qwen or Fibo (stubbed Tk).

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
    shutil.copy(t.ROOT / "workflows" / "fibo2-edit.json", Path(app.workflows_dir) / "fibo2-edit.json")
    app.cb_workflow["values"] = [gui.BUILTIN, "fibo2-edit.json"]

    def state(wf, mode, choice):
        app.v_workflow.set(wf)
        app.v_mode.set(mode)
        app.v_lmask.set(L[choice])
        app._update_feather_state()
        return app.w_feather["state"]

    # only "soft" uses the feather ("auto" left the menu 28.10.); Expand, Refine and Upscale have no edge feather at all
    assert "auto" not in L
    # Fill with an editor that ignores the mask (Fibo, Qwen) fades out to the crop's edge: no slider
    # (Show feather stays; the Tk stub has no packing to check)
    assert state("fibo2-edit.json", "inpaint", "soft") == "disabled"
    assert state("fibo2-edit.json", "remove", "soft") == "normal"
    assert state(gui.BUILTIN, "inpaint", "soft") == "normal"
    assert state("fibo2-edit.json", "inpaint", "selection") == "disabled"
    assert state("fibo2-edit.json", "inpaint", "none") == "disabled"
    assert state("fibo2-edit.json", "outpaint", "soft") == "disabled" and state(gui.BUILTIN, "outpaint", "soft") == "disabled"
    assert state(gui.BUILTIN, "refine", "soft") == "disabled" and state(gui.BUILTIN, "upscale", "soft") == "disabled"
    # changing the mode / loading a preset refreshes it by itself; an old preset with "auto" opens as soft
    app.v_workflow.set("fibo2-edit.json")
    app.v_lmask.set(L["soft"])
    app.v_mode.set("outpaint")
    app._on_mode_ui()
    assert app.w_feather["state"] == "disabled"
    app.v_mode.set("remove")
    app._on_mode_ui()
    assert app.w_feather["state"] == "normal"
    app._apply_settings({"mode": "remove", "layer_mask": "auto"})
    assert app.v_lmask.get() == L["soft"] and app.w_feather["state"] == "normal"
    app._apply_settings({"mode": "remove", "layer_mask": "none"})
    assert app.w_feather["state"] == "disabled"
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (feather state)")


if __name__ == "__main__":
    main()
