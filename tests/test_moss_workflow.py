"""The MOSS-Image inpainting workflow: valid API graph; the mask reaches the model through ImageToMask.

    python tests/test_moss_workflow.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge, workflows  # noqa: E402

WF = ROOT / "workflows" / "moss-image-inpaint.json"


def links_resolve(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def by_tag(g, tag):
    return [nid for nid, n in g.items() if tag in workflows._tags(n)]


def main():
    p = workflows.GenParams(prompt="a red scarf", seed=11, width=1024, height=768)
    tpl = workflows.load_template(WF)
    assert links_resolve(tpl)
    assert bridge.mask_is_used(tpl), "MOSS redraws only the mask"
    assert not bridge.prompt_phase_nodes(tpl) and workflows.lora_switches(tpl) == ["5"]   # the Lenovo LoRA is optional
    g, out = workflows.apply_template(tpl, p, "pic.png", "mask.png")
    mask_loader = by_tag(g, "mask")[0]
    to_mask = [nid for nid, n in g.items() if n["class_type"] == "ImageToMask"]
    assert len(to_mask) == 1 and g[to_mask[0]]["inputs"]["image"] == [mask_loader, 0]
    assert g[mask_loader]["inputs"]["image"] == "mask.png" and g[by_tag(g, "image")[0]]["inputs"]["image"] == "pic.png"
    assert g[by_tag(g, "prompt")[0]]["inputs"]["text"] == "a red scarf"      # no picture tag: MOSS needs none
    assert g[by_tag(g, "sampler")[0]]["inputs"]["seed"] == 11
    assert g[out]["class_type"] == "PreviewImage"
    # the result is the picture itself (outside the mask unchanged): ImageCompositeMasked pastes into pc:image
    comp = next(n for n in g.values() if n["class_type"] == "ImageCompositeMasked")
    assert comp["inputs"]["destination"] == [by_tag(g, "image")[0], 0]
    # no custom mask-box node (ComfyUI_essentials is avoided): the bridge cuts the crop around the selection itself
    assert not any(n["class_type"] in ("MaskBoundingBox+", "ImageScale") for n in g.values())
    assert g[next(k for k, n in g.items() if n["class_type"] == "VAEEncode")]["inputs"]["pixels"] == [by_tag(g, "image")[0], 0]
    # no leftovers of the original's showcase/preview branch; the window's mask grow/blur does that job
    assert not any(n["class_type"] in ("SaveImage", "AddLabel", "ImageStitch", "GrowMaskWithBlur") for n in g.values())
    # without the LoRA (the file may not be installed): the loader is gone and the model feeds straight on
    off = workflows.bypass_lora(g)
    assert "5" not in off and off["4"]["inputs"]["model"] == ["1", 0] and links_resolve(off)
    # through the bridge the same graph comes out
    req = bridge.Request(workflow=str(WF), params=p)
    graph, _ = bridge.Bridge._graph(object(), req, p, "pic.png", "mask.png", str(WF))
    assert graph == g
    print("ALL OK (MOSS workflow)")


if __name__ == "__main__":
    main()
