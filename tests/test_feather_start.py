"""Edge feather at start: the function's own starting value, not a fixed 2 % (stubbed Tk, no display needed).

Bug (28.10.): the feather is not part of the saved window state, so every start showed 2 %; Fibo Fill (10 %) and
Qwen Fill (4 %) looked hard until the function was chosen again. Decision of the user: option B, every start uses
the function's starting value.

    python tests/test_feather_start.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod


def start(model, mode, workflow, **extra):
    cfgmod.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfgmod.STATE_FILE.write_text(json.dumps({"model": model, "mode": mode, "workflow": workflow,
                                             "layer_mask": "soft", **extra}), encoding="utf-8")
    return gui.App(cfgmod.load())


def main():
    assert start("fibo", "inpaint", "fibo2-edit.json").v_feather.get() == 10.0
    assert start("qwen", "inpaint", "qwen-image-21-edit.json").v_feather.get() == 4.0
    assert start("qwen", "remove", "qwen-image-21-edit.json").v_feather.get() == 10.0
    # a function without a value of its own starts at 2 %, as after Reset; an old state with a feather does not win
    assert start("qwen", "txt2img", "qwen-image-21-t2i.json").v_feather.get() == 2.0
    assert start("fibo", "inpaint", "fibo2-edit.json", feather_pct=3.0).v_feather.get() == 10.0
    app = start("fibo", "inpaint", "fibo2-edit.json")
    assert app.lbl_feather.cget("text") == "10 %"
    cfgmod.STATE_FILE.unlink(missing_ok=True)
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (feather start)")


if __name__ == "__main__":
    main()
