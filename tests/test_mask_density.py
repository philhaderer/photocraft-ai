"""Mask density: Fill with Qwen and Fibo starts at 5 %, everything else at 100 %; the run sets it on the new layer's soft
mask in PhotoCraft (layer.layerMask.edit, PhotoCraft 0.17+), 100 % sets nothing (stubbed Tk, PhotoCraft and ComfyUI).

User 28.10.: the fills looked better with the layer mask's density turned down in PhotoCraft.

    python tests/test_mask_density.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reset_all as ra  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
import test_reference_mode as t  # noqa: E402

from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

ROOT = t.ROOT


def density_calls(wf, mode="inpaint", remove=False, density=5, layer_mask="soft"):
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, layers=2)
    b.comfy = t.FakeComfy()
    req = Request(mode=mode, workflow=str(ROOT / "workflows" / wf), enhance=False, remove=remove,
                  layer_mask=layer_mask, mask_density=density)
    req.params = workflows.GenParams(prompt="a boat", seed=7)
    b.run(req)
    log = [c for c, _ in pc.log]
    calls = [p for c, p in pc.log if c == "layer.layerMask.edit"]
    if calls:      # right after the mask was made
        assert log[log.index("layer.layerMask.edit") - 1] == "layer.layerMask.revealSelection", log
    return calls


def gui_checks():
    app = ra.make()
    for model in ("qwen", "fibo"):
        ra.go(app, model, "inpaint")
        assert app.v_density.get() == 5, (model, app.v_density.get())
        assert app._request().mask_density == 5
        ra.go(app, model, "remove")
        assert app.v_density.get() == 100, (model, app.v_density.get())    # Fill's 5 % does not travel on
    # shown and greyed out together with Edge feather
    ra.go(app, "qwen", "inpaint")
    assert app.w_density["state"] == "normal"
    app.v_lmask.set(ra.gui.LAYER_MASKS["none"])
    app._update_feather_state()
    assert app.w_density["state"] == "disabled"
    # Reset and settings: the function's own value again; a saved value comes back
    app.v_lmask.set(ra.gui.LAYER_MASKS["soft"])
    app.v_density.set(40)
    app.reset_settings()
    assert app.v_density.get() == 5
    app.v_density.set(37)
    assert app._collect()["mask_density"] == 37
    app._apply_settings({"mask_density": 60})
    assert app.v_density.get() == 60 and app.lbl_density.cget("text") == "60 %"


def main():
    gui_checks()
    for wf in ("qwen-image-21-edit.json", "fibo2-edit.json"):
        assert density_calls(wf) == [{"layer": density_calls(wf)[0]["layer"], "density": 5}]
        assert density_calls(wf, density=100) == []                      # 100 %: the mask as it is
        assert density_calls(wf, remove=True, density=100) == []
        assert [c["density"] for c in density_calls(wf, remove=True, density=30)] == [30]
        assert density_calls(wf, layer_mask="none") == []                # no mask, nothing to set
    print("ALL OK (mask density)")


if __name__ == "__main__":
    main()
