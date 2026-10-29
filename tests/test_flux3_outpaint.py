"""Flux 3 Expand with ausboss' outpaint LoRA (29.10., after Pixaroma's "14. Flux 3 Klein - Outpaint"): without the LoRA
Flux 3 slid or zoomed the picture instead of filling the margin. Expand runs its own graph (the LoRA at 1.5, 16 steps,
no reference slots), the new margin goes in mid grey (the colour the LoRA was trained on), the prompt is the LoRA's own
first sentence with the typed text after "Scene:", about 1 megapixel, Context 1.0 (the picture then fills
roughly the 45 to 93 % of the canvas the LoRA was made for). Stubbed PhotoCraft and ComfyUI.

    python tests/test_flux3_outpaint.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402

from pccomfy import bridge, imaging, manifest, models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

ROOT = T.ROOT
WF = ROOT / "workflows" / "flux3-klein-outpaint.json"
LORA = "Flux 3\\flux-3-image-klein-outpaint.safetensors"


def graph_checks():
    g = workflows.load_template(WF)
    lora = [n for n in g.values() if n["class_type"] == "LoraLoaderModelOnly"]
    assert len(lora) == 1 and lora[0]["inputs"]["lora_name"] == LORA and lora[0]["inputs"]["strength_model"] == 1.5
    assert "lora" not in workflows._tags(lora[0])          # fixed, not a switch of the window
    ks = next(n for n in g.values() if n["class_type"] == "KSampler")
    assert ks["inputs"]["steps"] == 16 and ks["inputs"]["model"] == [next(k for k, n in g.items() if n is lora[0]), 0]
    assert not bridge.has_tag(g, "ref") and bridge.has_tag(g, "image") and bridge.has_tag(g, "prompt")
    for n in g.values():                                    # every link points to a node of the graph
        for v in n["inputs"].values():
            if isinstance(v, list):
                assert v[0] in g, v
    # the model, the file list and the detection know it
    assert models.FLUX3.modes["outpaint"].workflow == WF.name
    assert models.FLUX3.modes["outpaint"].settings["base_res"] == 1024
    assert LORA in manifest.FILES and LORA in manifest.TABS["flux3"].modes["outpaint"].requires
    # the edit graph and the other functions stay as they were
    assert models.FLUX3.modes["edit"].workflow == "flux3-klein-edit.json"


def prompt_checks():
    k = imaging.Box(100, 0, 200, 100)
    p = bridge.outpaint_prompt(" a quiet harbour at dusk ", False, k, (300, 100), str(WF))
    assert p == bridge.FLUX3_OUTPAINT_PROMPT + " Scene: a quiet harbour at dusk", p
    assert bridge.outpaint_prompt("", False, k, (300, 100), str(WF)) == bridge.FLUX3_OUTPAINT_PROMPT
    assert "white" not in bridge.FLUX3_OUTPAINT_PROMPT.lower()
    # the other editors keep their white margin and words
    assert bridge.outpaint_prompt("", False, k, (300, 100), str(ROOT / "workflows" / "flux2-klein-edit.json")).startswith("Replace white")


def bridge_checks():
    for wf, colour in ((WF, (128, 128, 128)), (ROOT / "workflows" / "flux2-klein-edit.json", (255, 255, 255))):
        pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False, layers=2)
        pc.docs[0].layers[0]["img"].paste((255, 255, 255, 255), (T.W - 16, 0, T.W, T.H))    # new canvas on the right, white
        b.comfy = T.FakeComfy()
        req = Request(mode="outpaint", workflow=str(wf), preset="X", run_no=1, overlap=8, base_res=1024, context=1.0)
        req.params = workflows.GenParams(prompt="a stone wall", seed=5)
        res = b.run(req)
        assert res["layers"], wf
        up = next(im for name, im in b.comfy.uploads.items() if name.endswith("-image.png"))
        a = np.asarray(up.convert("RGB"), int)
        assert np.abs(a[:, -3:] - colour).max() <= 2, (wf.name, a[:, -3:].reshape(-1, 3)[:3])    # the margin
        assert np.abs(a[:, :3] - colour).max() > 20, wf.name                                          # the picture
        text = next(n["inputs"]["text"] for n in b.comfy.graphs[-1].values() if n["class_type"] == "CLIPTextEncode")
        if wf == WF:
            assert text == bridge.FLUX3_OUTPAINT_PROMPT + " Scene: a stone wall", text
            r = res["region"]                            # ~1 megapixel (a small test picture: at most twice its size)
            assert up.size == imaging.gen_size(r["w"], r["h"], 1024, multiple=32), (up.size, r)
        else:
            assert text.startswith("a stone wall, replace white"), text


def main():
    graph_checks()
    prompt_checks()
    bridge_checks()
    print("ALL OK (Flux 3 outpaint)")


if __name__ == "__main__":
    main()
