"""MOSS Edit (1.11.): the edit LoRA graph for Edit Canvas, Multi Image Edit and Remove Selection.

    python tests/test_moss_edit.py
"""
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import manifest, models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

WF = ROOT / "workflows" / "moss-image-edit.json"
LORA = "Moss\\moss_image_edit_lora_rank_64_bf16.safetensors"


def encoders(g):
    return [n for n in g.values() if n["class_type"] == "TextEncodeMOSSImageEdit"]


def main():
    g = json.loads(WF.read_text(encoding="utf-8"))
    assert all(str(v[0]) in g for n in g.values() for v in n["inputs"].values() if isinstance(v, list))
    assert len(encoders(g)) == 2 and all(n["inputs"]["edit_format"] == "Moss-Image-Edit" for n in encoders(g))   # both must match the LoRA
    assert any(n["class_type"] == "LoraLoaderModelOnly" and n["inputs"]["lora_name"] == LORA for n in g.values())
    assert workflows.lora_switches(g) == []    # no speed LoRA to switch off
    assert workflows.ref_slot_count(g) == 3 and not workflows.has_upscale_slot(g)
    s = g["40"]["inputs"]
    assert (s["steps"], s["cfg"], s["sampler_name"], s["scheduler"]) == (30, 4.0, "euler", "normal")    # the LoRA author's values

    m = models.MOSS
    assert list(m.modes) == ["txt2img", "edit", "multi_edit", "remove", "inpaint", "outpaint"]
    assert m.modes["edit"].workflow == m.modes["remove"].workflow == m.modes["multi_edit"].workflow == WF.name
    assert m.modes["multi_edit"].run_as == "edit" and m.modes["remove"].remove_text and m.max_refs == 3 and m.tag_style
    for mode in ("edit", "multi_edit", "remove"):
        assert LORA in manifest.mode_required("moss", mode) and manifest.FILES[LORA].sha256 and manifest.FILES[LORA].size
    assert LORA not in manifest.mode_required("moss", "txt2img")

    # Edit Canvas: no reference, so the three reference inputs are gone from both encoders
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(WF), preset="X", run_no=1)
    req.params = workflows.GenParams(prompt="Change only the sky to dusk.", seed=5)
    b.run(req)
    out = b.comfy.graphs[0]
    assert out["20"]["inputs"]["prompt"] == "Change only the sky to dusk."
    for n in encoders(out):
        assert [k for k in n["inputs"] if k.startswith("images.")] == ["images.image_0"]
    assert not any(k in out for k in ("11", "12", "13"))

    # Multi Image Edit: the picture first, then the references in order
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(WF), preset="X", run_no=1,
                  refs=[Image.new("RGB", (80, 60), (200, 10, 10)), Image.new("RGB", (60, 80), (10, 10, 200))])
    req.params = workflows.GenParams(prompt="Place the tent from image 2 in the meadow.", seed=5)
    b.run(req)
    out = b.comfy.graphs[0]
    for n in encoders(out):
        assert sorted(k for k in n["inputs"] if k.startswith("images.")) == ["images.image_0", "images.image_1", "images.image_2"]
    assert out["20"]["inputs"]["images.image_0"] == ["10", 0] and "13" not in out
    print("ALL OK (moss edit)")


if __name__ == "__main__":
    main()
