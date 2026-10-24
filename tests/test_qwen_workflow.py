"""The Qwen Image 2.1 edit workflow: a valid API graph with the tags the bridge fills, the picture tag and the turbo switch.

    python tests/test_qwen_workflow.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge, workflows  # noqa: E402

WF = ROOT / "workflows" / "qwen-image-21-edit.json"


def links_resolve(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def by_tag(g, tag):
    return [nid for nid, n in g.items() if tag in workflows._tags(n)]


def main():
    p = workflows.GenParams(prompt="a red scarf", seed=11, width=1024, height=768, batch=2)
    tpl = workflows.load_template(WF)
    assert links_resolve(tpl)
    # an instruction editor (never uses the mask), no text model, one picture
    assert not bridge.mask_is_used(tpl), "an editor must not use the mask"
    assert not bridge.prompt_phase_nodes(tpl) and not workflows.prompt_writers(tpl)
    g, out = workflows.apply_template(tpl, p, "pic.png", "mask.png")
    assert g[by_tag(g, "image")[0]]["inputs"]["image"] == "pic.png"
    assert g[by_tag(g, "mask")[0]]["inputs"]["image"] == "mask.png"
    lat = g[by_tag(g, "latent")[0]]["inputs"]
    assert (lat["width"], lat["height"], lat["batch_size"]) == (1024, 768, 2), lat
    smp = g[by_tag(g, "sampler")[0]]["inputs"]
    assert smp["seed"] == 11 and smp["denoise"] == 1.0 and smp["steps"] == 10 and smp["cfg"] == 1
    assert g[out]["class_type"] == "PreviewImage"
    enc = g[by_tag(g, "prompt")[0]]["inputs"]
    assert enc["images.image_1"] == [by_tag(g, "image")[0], 0] and enc["prompt"] == "<image1> a red scarf"
    try:   # one picture only: no reference slot
        workflows.apply_template(tpl, p, "pic.png", "mask.png", ref_name="ref.png")
    except ValueError as e:
        assert "reference slot" in str(e)
    else:
        raise AssertionError("Qwen has no reference slot")

    # the turbo switch: 10 steps with the LoRA, 25 without
    assert workflows.lora_switches(tpl) == ["2"]
    off = workflows.bypass_lora(g)
    assert not any(n["class_type"] == "LoraLoaderModelOnly" for n in off.values())
    assert off[by_tag(off, "sampler")[0]]["inputs"]["steps"] == 25 and links_resolve(off)
    cache = next(n for n in off.values() if n["class_type"] == "QwenImage21Cache")
    assert off[str(cache["inputs"]["model"][0])]["class_type"] == "UNETLoader"
    for turbo, steps in ((True, 10), (False, 25)):
        req = bridge.Request(workflow=str(WF), params=p, turbo=turbo)
        graph, _ = bridge.Bridge._graph(object(), req, p, "pic.png", "mask.png", str(WF))
        assert graph[by_tag(graph, "sampler")[0]]["inputs"]["steps"] == steps
    print("ALL OK (Qwen workflow)")


if __name__ == "__main__":
    main()
