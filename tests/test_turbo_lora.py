"""Turbo LoRA off: the pc:lora loader leaves the graph and the sampler runs the workflow's full-step values.

    python tests/test_turbo_lora.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge, workflows  # noqa: E402

WF = ROOT / "workflows"


def links_resolve(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def turbo_template():
    """A minimal turbo workflow: model -> LoRA -> cache -> sampler (10 steps, 25 without the LoRA)."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "m.safetensors"}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "t.safetensors", "model": ["1", 0]},
              "_meta": {"title": "pc:lora turbo"}},
        "3": {"class_type": "Cache", "inputs": {"model": ["2", 0]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "x.png"}, "_meta": {"title": "pc:image"}},
        "5": {"class_type": "LoadImage", "inputs": {"image": "x.png"}, "_meta": {"title": "pc:mask"}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["3", 0], "seed": 1, "steps": 10, "cfg": 1, "denoise": 1},
              "_meta": {"title": "pc:sampler", "pc_no_lora": {"steps": 25}}},
        "7": {"class_type": "PreviewImage", "inputs": {"images": ["6", 0]}, "_meta": {"title": "pc:output"}},
    }


def main():
    tpl = turbo_template()
    assert workflows.lora_switches(tpl) == ["2"], workflows.lora_switches(tpl)
    g, out = workflows.apply_template(tpl, workflows.GenParams(prompt="x", seed=7), "i.png", "m.png")
    assert g["6"]["inputs"]["steps"] == 10 and g["6"]["inputs"]["seed"] == 7

    off = workflows.bypass_lora(g)
    assert "2" not in off and not workflows.lora_switches(off)
    assert off["3"]["inputs"]["model"] == ["1", 0], off["3"]          # the cache now reads the plain model
    assert off["6"]["inputs"]["steps"] == 25 and off["6"]["inputs"]["seed"] == 7
    assert links_resolve(off) and out in off
    assert workflows.bypass_lora(off) == off                          # idempotent
    assert "2" in g and g["6"]["inputs"]["steps"] == 10               # the input is untouched

    # a sampler with no pc_no_lora keeps its values; two LoRAs in a row both drop out
    chain = {"1": {"class_type": "UNETLoader", "inputs": {}},
             "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0]}, "_meta": {"title": "pc:lora a"}},
             "3": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["2", 0]}, "_meta": {"title": "pc:lora b"}},
             "4": {"class_type": "KSampler", "inputs": {"model": ["3", 0], "steps": 8}, "_meta": {"title": "pc:sampler"}}}
    c = workflows.bypass_lora(chain)
    assert sorted(c) == ["1", "4"] and c["4"]["inputs"]["model"] == ["1", 0] and c["4"]["inputs"]["steps"] == 8, c

    # a graph without a pc:lora node comes back unchanged
    t = workflows.load_template(WF / "fibo2-edit.json")
    assert not workflows.lora_switches(t) and workflows.bypass_lora(t) == t

    # through the bridge: the Request decides
    with tempfile.TemporaryDirectory() as d:
        wf = str(Path(d) / "turbo.json")
        Path(wf).write_text(json.dumps(tpl), encoding="utf-8")
        p = workflows.GenParams(prompt="x", seed=3)
        for turbo, steps, has_lora in ((True, 10, True), (False, 25, False)):
            req = bridge.Request(workflow=wf, params=p, turbo=turbo)
            graph, _ = bridge.Bridge._graph(object(), req, p, "i.png", "m.png", wf)
            assert graph["6"]["inputs"]["steps"] == steps, (turbo, graph["6"]["inputs"])
            assert any(n["class_type"] == "LoraLoaderModelOnly" for n in graph.values()) == has_lora
            assert links_resolve(graph)
    # Fibo ignores the switch
    fibo = str(WF / "fibo2-edit.json")
    on, _ = bridge.Bridge._graph(object(), bridge.Request(workflow=fibo, params=p, turbo=True), p, "i.png", "m.png", fibo)
    off_, _ = bridge.Bridge._graph(object(), bridge.Request(workflow=fibo, params=p, turbo=False), p, "i.png", "m.png", fibo)
    assert on == off_
    # the Flux upscale workflows: their LoRA can be switched off, the rest of the graph stays whole
    for name, loader, label in (("flux3-klein-upscale.json", "9", "Restore LoRA"), ("flux2-klein-upscale.json", "191", "Ultra real LoRA")):
        tpl = workflows.load_template(WF / name)
        assert workflows.lora_switches(tpl) == [loader] and tpl[loader]["_meta"]["pc_lora_label"] == label, name
        off = workflows.bypass_lora(tpl)
        assert loader not in off and links_resolve(off), name
        users = [n for n in off.values() if any(isinstance(v, list) and v[0] == tpl[loader]["inputs"]["model"][0]
                                                 for k, v in n["inputs"].items() if k == "model")]
        assert users, name                                            # the sampler's model is the plain one now
        assert len(off) == len(tpl) - 1, name
    print("ALL OK (turbo LoRA)")


if __name__ == "__main__":
    main()
