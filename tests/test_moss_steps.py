"""MOSS Text to image: switching the DMD2 LoRA on or off sets Steps and CFG to the workflow's values for that case (8 / 1.5
with it, 25 / 2.5 without: pc_no_lora), so nothing stale is sent as an override; the Steps field has MOSS's tooltip.

    python tests/test_moss_steps.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod


def main():
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in gui.models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    app.v_model.set("moss")
    app.v_mode.set("txt2img")
    app._on_model()
    # the start of MOSS Text to image (user 29.10.): DMD2 off, UltraReal on, SLG off, no LLM, 25 steps
    labels = [st["label"] for st in app._stages()]
    assert "SLG" in labels[1] or "Skip" in labels[1], labels
    assert (app.v_turbo.get(), app.v_stage.get(), app.v_stage2.get(), app.v_enhance.get()) == (False, True, False, False)
    assert app.v_steps.get() == 25, app.v_steps.get()
    app.v_turbo.set(True)
    app._on_turbo()
    assert (app.v_steps.get(), app.v_cfg.get()) == (8, 1.5), (app.v_steps.get(), app.v_cfg.get())
    app.v_turbo.set(False)
    app._on_turbo()
    assert (app.v_steps.get(), app.v_cfg.get()) == (25, 2.5), (app.v_steps.get(), app.v_cfg.get())
    assert app._sampler_override() == {}, app._sampler_override()       # the workflow's own values: no override
    assert app.w_lora_str["state"] == "disabled"
    app.v_turbo.set(True)
    app._on_turbo()
    assert app.v_steps.get() == 8 and app.w_lora_str["state"] == "normal"
    assert app.tt_steps.text == gui.models.MOSS_STEPS_TIP
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.tt_steps.text == ""                                       # other models: no Steps tooltip
    print("test_moss_steps: ok")


if __name__ == "__main__":
    main()
