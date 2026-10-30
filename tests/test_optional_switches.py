"""Modes that need no extra file with their standard settings keep working without it (user 30.10.): Flux 3 Upscale runs
without the SeedVR2 files because its SeedVR2 pre-cleaning starts off. The switch itself is greyed out while they are
missing (its tooltip names them) and cannot be on; a setting loaded from history, a preset or a saved page that wants it on
is switched off and named in the notes. A speed LoRA switch behaves the same. Stubbed Tk.

    python tests/test_optional_switches.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_settings_ui as su  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod, inventory, manifest, td = su.gui, su.cfgmod, su.inventory, su.manifest, su.td
# ComfyUI lists every node class of every workflow it can run (the test's own set is only what the manifest names)
_CLASSES = {n["class_type"] for f in (ROOT / "workflows").glob("*.json") for n in json.loads(f.read_text(encoding="utf-8")).values()}
NODES = su.NODES | _CLASSES


def go(app, inv):
    app._apply_refresh({"_detect": True, "_inv": inv})
    app.v_model.set("flux3")
    app.v_mode.set("upscale")
    app._on_model()


def main():
    # the mode: ready without SeedVR2, the files are optional
    inv = inventory.Inventory(su.lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), NODES)
    assert inv.mode_status("flux3", "upscale").state == "ready"
    assert "seedvr2_3b_int8_convrot.safetensors" in manifest.mode_optional("flux3", "upscale")
    assert not set(n for n in manifest.mode_nodes("flux3", "upscale") if n.startswith("SeedVR2"))      # the nodes too

    # the graph a run sends with the switch off has no SeedVR2 loader: nothing is missing for ComfyUI either
    from pccomfy import workflows
    tpl = workflows.load_template(ROOT / "workflows" / "flux3-klein-upscale.json")
    assert inv.check_workflow(workflows.bypass_stage(tpl)) == ([], []), inv.check_workflow(workflows.bypass_stage(tpl))
    assert inv.check_workflow(tpl)[0] == [("unet", "seedvr2_3b_int8_convrot.safetensors")]       # switched on it would be

    # the window: the SeedVR2 switch is grey, off, with the file in its tooltip; the mode is usable
    app = su.make_app()
    go(app, inv)
    assert app.v_workflow.get() == "flux3-klein-upscale.json" and app._preflight() == []
    assert app.stage_cbs[0]["state"] == "disabled" and app.v_stage.get() is False
    assert "seedvr2_3b_int8_convrot.safetensors" in app.stage_tips[0].text and "settings" in app.stage_tips[0].text
    assert app.cb_turbo["state"] == "normal"                                   # the Restore LoRA is there
    # a loaded setting that wants SeedVR2 on: off again, named in the notes (the history / preset message)
    notes = app._apply_settings({"stage_on": True})
    assert app.v_stage.get() is False and notes and "SeedVR2 pre-cleaning needs seedvr2" in notes[0], notes

    # the files there: the switch is usable and stays on when asked
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES)})
    assert app.stage_cbs[0]["state"] == "normal"
    assert app._apply_settings({"stage_on": True}) == [] and app.v_stage.get() is True

    # a speed LoRA switch: Qwen's Turbo LoRA missing: greyed out, off, a loaded "on" is named
    lists = td.full_lists()
    lists["lora"].remove("qwen" + chr(92) + "qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors")
    app = su.make_app()
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists, NODES)})
    app.v_model.set("qwen")
    app.v_mode.set("edit")
    app._on_model()
    assert app.cb_turbo["state"] == "disabled" and app.v_turbo.get() is False
    notes = app._apply_settings({"turbo": True})
    assert app.v_turbo.get() is False and notes and "needs" in notes[0], notes
    print("ALL OK (optional switches)")


if __name__ == "__main__":
    main()
