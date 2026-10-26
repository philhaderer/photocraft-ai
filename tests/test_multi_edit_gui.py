"""Multi Image Edit in the window (stubbed Tk): the mode replaces "Insert reference image", the slots show only in it,
the request runs as a whole-image edit, old presets with the removed mode fall back.

    python tests/test_multi_edit_gui.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod


def main():
    keys = [k for k, _ in gui.MODE_LABELS]
    assert ("multi_edit", "Multi Image Edit") in gui.MODE_LABELS and "reference" not in keys
    assert keys.index("multi_edit") == keys.index("outpaint") + 1        # where "Insert reference image" stood
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    for f in ("qwen-image-21-edit.json", "fibo2-edit.json", "flux2-klein-edit.json", "flux3-klein-edit.json", "flux2-klein-t2i.json"):
        if (t.ROOT / "workflows" / f).exists():
            shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    # every model that takes references has the mode, the others do not
    for key in ("qwen", "fibo", "flux2", "flux3"):
        m = next(x for x in gui.models.MODELS if x.key == key)
        assert "multi_edit" in m.modes and m.modes["multi_edit"].run_as == "edit" and m.max_refs > 0, key
        assert m.modes["multi_edit"].workflow == m.modes["edit"].workflow, key
    for m in gui.models.MODELS:
        if m.max_refs == 0:
            assert "multi_edit" not in m.modes, m.key
    # the window: the request runs as an edit, carries no mask use, and the mode is kept in the state
    app.cb_workflow["values"] = [gui.BUILTIN, "qwen-image-21-edit.json"]
    app.v_workflow.set("qwen-image-21-edit.json")
    app.v_model.set("qwen")
    app.v_mode.set("multi_edit")
    app._on_model()
    req = app._request()
    assert req.mode == "edit" and app.v_mode.get() == "multi_edit"
    s = app._collect()
    assert s["mode"] == "multi_edit"
    app._save_state(req)
    import json
    assert json.loads((Path(t.TMP) / "state.json").read_text(encoding="utf-8"))["mode"] == "multi_edit"
    # an old preset with the removed mode does not crash: the first mode of the tab
    old = dict(s, mode="reference", ref_style="simple", ref_collage=True, ref_cutout=True)
    app._apply_settings(old)
    assert app.v_mode.get() in app._model().modes and app.v_mode.get() != "reference"
    assert not hasattr(app, "f_ref") and not hasattr(app, "v_refstyle")
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (multi image edit gui)")


if __name__ == "__main__":
    main()
