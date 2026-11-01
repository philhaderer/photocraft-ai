"""MOSS in the bridge: Text to image on the whole canvas (a selection is ignored), the LoRA files under the names the
server lists, the extra stages, and the model/options in the name of an upscaled document.

    python tests/test_moss_modes.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import BridgeError, Request  # noqa: E402
import test_reference_mode as T  # noqa: E402

T2I = str(ROOT / "workflows" / "moss-image-t2i.json")
FILL = str(ROOT / "workflows" / "moss-image-inpaint.json")
SERVER = ["Moss\\lenovo_moss.safetensors", "Moss\\lora_dmd2.safetensors", "qwen\\x.safetensors"]


class Comfy(T.FakeComfy):
    def __init__(self, loras=SERVER):
        super().__init__()
        self._loras = loras

    def loras(self):
        return self._loras


def run(mode="txt2img", wf=T2I, prompt="a cat on a sofa", with_sel=True, loras=SERVER, **kw):
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp, with_sel=with_sel)
    b.comfy = Comfy(loras)
    if wf == T2I:
        kw.setdefault("stage_on", False)      # the first stage of the text-to-image graph is the 4-step LoRA: off in the window by default
    req = Request(mode=mode, workflow=wf, preset="MOSS Image Text", run_no=1, **kw)
    req.params = workflows.GenParams(prompt=prompt, seed=5, width=64, height=64)
    return pc, b, b.run(req)


def main():
    # Text to image: the whole canvas, whatever is selected; the latent has the size of the canvas
    for sel in (True, False):
        pc, b, res = run(with_sel=sel)
        assert res["layers"] and res["region"] == {"x": 0, "y": 0, "w": T.W, "h": T.H}, res["region"]
        g = b.comfy.graphs[0]
        lat = next(n for n in g.values() if n["class_type"] == "EmptyFlux2LatentImage")["inputs"]
        assert lat["width"] % 16 == 0 and lat["height"] % 16 == 0 and lat["width"] * lat["height"] > 0
        assert g["11"]["inputs"]["prompt"] == "a cat on a sofa"                  # the prompt enhancer gets the typed text
    # without the enhancer the typed text goes straight to the encoder
    _, b, _ = run(enhance=False)
    g = b.comfy.graphs[0]
    assert "11" not in g and g["4"]["inputs"]["text"] == "a cat on a sofa"
    for kw, msg in (({"enhance": False}, "Describe the picture"), ({}, "Type an instruction")):
        try:
            run(prompt="", **kw)
            raise AssertionError("empty prompt accepted")
        except BridgeError as e:
            assert msg in str(e), str(e)

    # the LoRA files are sent under the names ComfyUI lists; a missing file stops the run with its name
    _, b, _ = run()
    g = b.comfy.graphs[0]
    assert g["6"]["inputs"]["lora_name"] == "Moss\\lora_dmd2.safetensors"
    _, b, _ = run(wf=FILL, mode="inpaint", loras=["Moss/lenovo_moss.safetensors", "moss/LORA_DMD2.safetensors"], stage_on=True)
    g = b.comfy.graphs[0]
    assert g["6"]["inputs"]["lora_name"] == "moss/LORA_DMD2.safetensors" and g["5"]["inputs"]["lora_name"] == "Moss/lenovo_moss.safetensors"
    try:
        run(loras=["Moss\\lenovo_moss.safetensors"])
        raise AssertionError("missing LoRA accepted")
    except BridgeError as e:
        assert "lora_dmd2" in str(e)
    # DMD2 off: the file is not needed at all
    _, b, _ = run(loras=["Moss\\lenovo_moss.safetensors"], turbo=False, stages_off=["5"])
    g = b.comfy.graphs[0]
    assert "6" not in g and "5" not in g and g["7"]["inputs"]["model"] == ["1", 0]

    # the stages of the text-to-image graph: the 4-step LoRA is the first (stage_on, off), UltraReal and SLG follow (stages_off)
    _, b, _ = run(stages_off=["7"])
    g = b.comfy.graphs[0]
    assert "5" in g and "7" not in g and "9" not in g and g["40"]["inputs"]["model"] == ["5", 0]
    _, b, _ = run(stages_off=["5"])
    g = b.comfy.graphs[0]
    assert "5" not in g and "7" in g and g["7"]["inputs"]["model"] == ["6", 0]

    # the Lenovo LoRA has a strength slider of its own; the DMD2 strength is not touched
    for wf in (T2I, FILL):
        _, b, _ = run(wf=wf, mode="inpaint" if wf == FILL else "txt2img", stage_on=(wf == FILL), stage_strengths={"5": 0.6})
        g = b.comfy.graphs[0]
        assert g["5"]["inputs"]["strength_model"] == 0.6 and g["6"]["inputs"]["strength_model"] == 1.0
    assert [s["strength"] for s in workflows.stage_info(workflows.load_template(T2I))] == [1.0, 1.0, None]

    # typed steps / CFG reach the sampler
    _, b, _ = run(sampler_override={"steps": 12, "cfg": 2.0})
    ks = b.comfy.graphs[0]["40"]["inputs"]
    assert (ks["steps"], ks["cfg"]) == (12, 2.0)
    # colour pull-back runs through a Fill without trouble (the fake model draws a loud green picture)
    _, b, res = run(wf=FILL, mode="inpaint", match=0.5, stage_on=True)
    assert res["layers"]
    print("ALL OK (MOSS modes)")


if __name__ == "__main__":
    main()
