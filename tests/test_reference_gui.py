"""Insert reference image in the window (stubbed Tk): the mode, its box, the text model switched off, state/preset.

    python tests/test_reference_gui.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
L = gui.LAYER_MASKS


def main():
    assert ("reference", "Insert reference image") in gui.MODE_LABELS
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    for f in ("fibo2-edit-plain.json", "fibo2-edit-vgl-bionic-qwen35-9b.json"):
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN, "fibo2-edit-plain.json", "fibo2-edit-vgl-bionic-qwen35-9b.json"]
    shown = []
    app.f_ref.pack = lambda *a, **k: shown.append("on")
    app.f_ref.pack_forget = lambda: shown.append("off")

    # the box appears only in this mode
    app.v_workflow.set("fibo2-edit-vgl-bionic-qwen35-9b.json")
    app.v_lmask.set(L["auto"])
    app.v_mode.set("inpaint")
    app._on_mode()
    assert shown[-1] == "off" and app.cb_enhance["state"] == "normal"   # text model usable in Fill
    app.v_mode.set("reference")
    app._on_mode()
    assert shown[-1] == "on"
    assert app.cb_enhance["state"] == "disabled"                         # not used in reference mode
    assert app.w_feather["state"] == "disabled"                          # auto = no layer mask, like Fill
    assert app.v_denoise.get() == 1.0
    app.v_mode.set("outpaint")
    app._on_mode()
    assert shown[-1] == "off" and app.cb_enhance["state"] == "normal"

    # the request carries the mode and the placement switch; state and presets keep it
    app.v_mode.set("reference")
    app.v_collage.set(False)
    req = app._request()
    assert req.mode == "reference" and req.ref_collage is False and req.layer_mask == "auto"
    s = app._collect()
    assert s["mode"] == "reference" and s["ref_collage"] is False
    app.v_collage.set(True)
    app._apply_settings(dict(s))
    assert app.v_collage.get() is False and app.v_mode.get() == "reference" and shown[-1] == "on"
    assert app._request().ref_collage is False
    # the window state keeps the switch too (it was lost on restart)
    app._save_state(app._request())
    import json as _json
    assert _json.loads((Path(t.TMP) / "state.json").read_text(encoding="utf-8"))["ref_collage"] is False
    # the style: classic by default; simple greys out the rough placement; kept by request, preset and state
    assert app._request().ref_style == "classic" and app.cb_collage["state"] == "normal"
    app.v_refstyle.set(gui.REF_STYLES["simple"])
    app._update_availability()
    assert app._request().ref_style == "simple" and app.cb_collage["state"] == "disabled"
    s = app._collect()
    assert s["ref_style"] == "simple"
    app.v_refstyle.set(gui.REF_STYLES["classic"])
    app._apply_settings(dict(s))
    assert app._request().ref_style == "simple"
    app._save_state(app._request())
    assert _json.loads((Path(t.TMP) / "state.json").read_text(encoding="utf-8"))["ref_style"] == "simple"
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (reference gui)")


if __name__ == "__main__":
    main()
