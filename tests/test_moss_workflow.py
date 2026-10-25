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
    assert not bridge.prompt_phase_nodes(tpl) and workflows.lora_switches(tpl) == ["6"]   # the DMD2 speed LoRA is the model's own
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
    assert "6" not in off and off["5"]["inputs"]["model"] == ["1", 0] and links_resolve(off)
    ks = off[by_tag(off, "sampler")[0]]["inputs"]
    assert (ks["steps"], ks["cfg"]) == (25, 2.5)            # without the DMD2 LoRA: the full recipe
    on = g[by_tag(g, "sampler")[0]]["inputs"]
    assert (on["steps"], on["cfg"]) == (8, 1.5)              # with it: 8 steps, CFG 1.5
    # the Lenovo LoRA and the skip-layer guidance are switches; both start off
    sw = workflows.stage_switches(tpl)
    assert [l for _, l in sw] == ["Lenovo UltraReal LoRA", "Skip-layer guidance (SLG)"]
    assert [workflows.stage_default_on(tpl, n) for n, _ in sw] == [False, False]
    for off_ids in (["5"], ["7"], ["5", "7"]):
        gg = workflows.bypass_stage(tpl, off_ids)
        assert links_resolve(gg) and all(i not in gg for i in off_ids)
    both = workflows.bypass_stage(tpl, ["5", "7"])
    assert both["4"]["inputs"]["model"] == ["6", 0]
    both_nodmd = workflows.bypass_stage(workflows.bypass_lora(tpl), ["5", "7"])
    assert both_nodmd["4"]["inputs"]["model"] == ["1", 0] and links_resolve(both_nodmd)
    assert workflows.bypass_stage(tpl, ["7"])["4"]["inputs"]["model"] == ["5", 0]
    # the LoRA files are found under the names the server lists (Windows: backslash, folder case)
    fixed, missing = workflows.fix_lora_names(tpl, ["Moss/lenovo_moss.safetensors", "moss/LORA_DMD2.safetensors", "other/x.safetensors"])
    assert not missing and fixed["5"]["inputs"]["lora_name"] == "Moss/lenovo_moss.safetensors" and fixed["6"]["inputs"]["lora_name"] == "moss/LORA_DMD2.safetensors"
    assert workflows.fix_lora_names(tpl, ["a/b.safetensors"])[1] == ["Moss\\lora_dmd2.safetensors", "Moss\\lenovo_moss.safetensors"] or True
    _, missing = workflows.fix_lora_names(tpl, ["a/b.safetensors"])
    assert sorted(missing) == sorted(["Moss\\lora_dmd2.safetensors", "Moss\\lenovo_moss.safetensors"]), missing
    # through the bridge the same graph comes out
    req = bridge.Request(workflow=str(WF), params=p)
    graph, _ = bridge.Bridge._graph(object(), req, p, "pic.png", "mask.png", str(WF))
    assert graph == g
    # Text to image: a latent of the window's size, the prompt enhancer is the text model and can be bypassed
    t = workflows.load_template(ROOT / "workflows" / "moss-image-t2i.json")
    assert links_resolve(t) and not bridge.mask_is_used(t) and bridge.prompt_phase_nodes(t) >= {"11", "2", "14"}
    tg, tout = workflows.apply_template(t, workflows.GenParams(prompt="a cat", seed=5, width=1280, height=768, batch=2), None, None)
    lat = tg[by_tag(tg, "latent")[0]]["inputs"]
    assert (lat["width"], lat["height"], lat["batch_size"]) == (1280, 768, 2) and tg[tout]["class_type"] == "PreviewImage"
    assert tg["11"]["inputs"]["prompt"] == "a cat"
    plain = workflows.bypass_prompt_writer(t, "a cat")
    assert plain["4"]["inputs"]["text"] == "a cat" and "11" not in plain and links_resolve(plain)
    print("ALL OK (MOSS workflow)")


if __name__ == "__main__":
    main()
