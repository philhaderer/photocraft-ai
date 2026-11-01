"""MOSS Fill and Expand after Inpainting v10 (1.11.): the graph of the tick "v10 graph" and what the bridge sends for it.

    python tests/test_moss_v10.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("PCCOMFY_HOME", tempfile.mkdtemp(prefix="pccomfy-v10-"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import manifest, models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

A = ROOT / "workflows" / "moss-image-inpaint.json"
B = ROOT / "workflows" / "moss-image-inpaint-v10.json"


def graphs():
    a, b = json.loads(A.read_text(encoding="utf-8")), json.loads(B.read_text(encoding="utf-8"))
    assert all(str(v[0]) in b for n in b.values() for v in n["inputs"].values() if isinstance(v, list))
    # the window shows the stages and the sampler values of the plugin graph; the request substitutes the v10 graph, so the
    # ids of the stages and the sampler must be the same in both
    assert [s["id"] for s in workflows.stage_info(a)] == [s["id"] for s in workflows.stage_info(b)] == ["5", "7"]
    assert workflows.main_sampler(a) == workflows.main_sampler(b) == "40"
    sa, sb = workflows.sampler_values(workflows.bypass_lora(a)), workflows.sampler_values(b)
    assert sa == sb and (sb["steps"], sb["cfg"], sb["sampler"], sb["scheduler"]) == (25, 2.5, "er_sde", "simple")   # v10's own values
    assert workflows.full_canvas(b) and not workflows.full_canvas(a)
    assert {n["class_type"] for n in b.values()} >= {"GrowMaskWithBlur", "MaskBoundingBox+", "DifferentialDiffusion", "SetLatentNoiseMask"}
    assert b["31"]["inputs"]["padding"] == 256 and b["32"]["inputs"]["megapixels"] == 1.5
    assert manifest.node_pack("GrowMaskWithBlur") and manifest.node_pack("MaskBoundingBox+")


def models_():
    m = models.MOSS
    # Fill and Expand run the edit LoRA since 1.11. (the v10 graphs did not fit the selection); both v10 graphs are parked
    assert m.modes["inpaint"].workflow == m.modes["outpaint"].workflow == "moss-image-edit.json"
    assert {A.name, B.name} <= models.PARKED_WORKFLOWS and models.PARKED_EXPAND["moss"].workflow == A.name
    lora = "Moss" + chr(92) + "moss_image_edit_lora_rank_64_bf16.safetensors"
    for mode in ("inpaint", "outpaint"):
        assert lora in manifest.mode_required("moss", mode)


def bridge_run(wf, mode="inpaint"):
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp)
    b.comfy = T.FakeComfy()
    req = Request(mode=mode, workflow=str(wf), preset="X", run_no=1, base_res=1216, context=0.4, mask_grow=8, mask_blur=16)
    req.params = workflows.GenParams(prompt="a red silk scarf", seed=5)
    res = b.run(req)
    return b, res


def run_both():
    b, res = bridge_run(A)                                          # the plugin's own cut-out: the part, scaled to the base resolution
    sizes_a = {k: v.size for k, v in b.comfy.uploads.items()}
    assert next(v for k, v in sizes_a.items() if k.endswith("-image.png")) == next(v for k, v in sizes_a.items() if k.endswith("-mask.png"))
    b, res = bridge_run(B)
    sizes_b = {k: v.size for k, v in b.comfy.uploads.items()}
    pic = next(v for k, v in sizes_b.items() if k.endswith("-image.png"))
    msk = next(v for k, v in sizes_b.items() if k.endswith("-mask.png"))
    assert pic == msk == (T.W, T.H), sizes_b                       # v10: the whole picture and the whole selection, at their own size
    assert res["region"] == {"x": 0, "y": 0, "w": T.W, "h": T.H}, res["region"]
    g = b.comfy.graphs[0]
    assert g["20"]["inputs"]["text"] == "a red silk scarf" and g["40"]["inputs"]["steps"] == 25
    # the mask reached the graph as it is: no grow and no blur from the window (the graph's own KJ node does that)
    m = b.comfy.uploads[g["11"]["inputs"]["image"]].convert("L")
    assert set(m.getdata()) <= {0, 255}, "the selection is sent unsoftened"


def gui_tick():
    try:
        import tkinter
        tkinter.Tk().destroy()
    except Exception as e:
        print(f"(tick not tested: no Tk window: {e})")
        return
    from pccomfy import config as cfgmod
    from pccomfy import gui
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.cb_workflow["values"] = [gui.BUILTIN] + sorted({w for m in models.MODELS for w in m.workflows()}) + [gui.V10_WORKFLOW]
    for mode, shown in (("inpaint", True), ("outpaint", False), ("edit", False), ("txt2img", False)):
        app.v_model.set("moss")
        app.v_mode.set(mode)
        app._on_model()
        app.root.update()
        assert app._v10_shown is shown and not app.v_v10.get(), mode
        assert "v10" not in (app._request().workflow or "")
    app.v_mode.set("inpaint")
    app._on_model()
    app.v_v10.set(True)
    r = app._request()
    assert r.workflow.endswith(gui.V10_WORKFLOW) and r.sampler_override == {} and r.turbo is False and r.stage_on is True and r.stages_off == ["7"]
    app.v_model.set("qwen")
    app._on_model()
    app.root.update()
    assert not app._v10_shown and not app.v_v10.get(), "MOSS only; off again outside"


def main():
    graphs()
    models_()
    run_both()
    gui_tick()
    print("ALL OK (moss v10)")


if __name__ == "__main__":
    main()
