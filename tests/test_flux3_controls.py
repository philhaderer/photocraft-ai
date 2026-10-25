"""Flux 3 controls: LoRA strength, SeedVR2 stage switch, detail mix.

    python tests/test_flux3_controls.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402
from pccomfy import bridge, workflows  # noqa: E402
import test_reference_mode as T  # noqa: E402


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def main():
    f3 = workflows.load_template(ROOT / "workflows" / "flux3-klein-upscale.json")
    assert workflows.lora_strength(f3) == 1.0
    g = workflows.set_lora_strength(f3, 0.4)
    assert workflows.lora_strength(g) == 0.4 and workflows.lora_strength(f3) == 1.0
    q = workflows.load_template(ROOT / "workflows" / "qwen-image-21-edit.json")
    assert workflows.lora_strength(q) == 1.0 and workflows.lora_strength(workflows.set_lora_strength(q, 0.7)) == 0.7
    assert workflows.lora_strength(workflows.load_template(ROOT / "workflows" / "flux2-klein-upscale.json")) == 0.3
    assert workflows.lora_strength(workflows.load_template(ROOT / "workflows" / "fibo2-edit-plain.json")) is None

    assert [l for _, l in workflows.stage_switches(f3)] == ["SeedVR2 pre-cleaning"]
    off = workflows.bypass_stage(f3)
    assert links_ok(off) and len(off) == len(f3) - 11 and not any("SeedVR2" in n["class_type"] for n in off.values())
    assert off["153"]["inputs"]["image"] == ["2", 0]
    assert workflows.stage_switches(off) and links_ok(workflows.apply_template(off, workflows.GenParams(prompt="x"), "a.png", None, None)[0])

    # through the bridge: strength and stage reach the graph
    p = workflows.GenParams(prompt="", seed=1)
    wf = str(ROOT / "workflows" / "flux3-klein-upscale.json")
    req = bridge.Request(mode="upscale", workflow=wf, params=p, lora_strength=0.5, stage_on=False)
    p.extra["megapixels"] = 2.0
    graph, _ = bridge.Bridge._graph(object(), req, p, "pic.png", None, wf)
    assert "10" not in graph and workflows.lora_strength(graph) == 0.5

    # detail mix: 0 keeps the plain original
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp)
    b.comfy = T.FakeComfy()
    r = bridge.Request(mode="refine", workflow=wf, detail=0.0)
    r.params = workflows.GenParams(prompt="", seed=2)
    res = b.run(r)
    assert res["layers"]
    print("ALL OK (flux3 controls)")


if __name__ == "__main__":
    main()
