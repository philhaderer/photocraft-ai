"""Flux 3 Upscale built from standard nodes only (test variant A2 of the refine A/B test, 1.6 option b).

    python tests/test_upscale_std.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

WF = ROOT / "workflows" / "flux3-klein-upscale-std.json"


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def main():
    g = json.loads(WF.read_text(encoding="utf-8"))
    assert not any("AUSBOSS" in n["class_type"] for n in g.values()) and links_ok(g)
    assert workflows.has_upscale_slot(g) and workflows.lora_strength(g) == 0.5
    assert [l for _, l in workflows.stage_switches(g)] == ["SeedVR2 pre-cleaning"]
    off = workflows.bypass_stage(g)
    assert links_ok(off) and not any("SeedVR2" in n["class_type"] for n in off.values())   # 166 (size) survives the switch
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="upscale", workflow=str(WF), preset="X", run_no=1, scale=1.5, stage_on=False)
    req.params = workflows.GenParams(prompt="", seed=7)
    b.run(req)
    out = b.comfy.graphs[0]
    assert out["5"]["inputs"]["value"] == 7 and links_ok(out)
    assert out["159"]["inputs"]["text"].startswith("Restore the photo")
    assert out["3"]["inputs"]["megapixels"] > 0
    print("ALL OK (upscale standard nodes)")


if __name__ == "__main__":
    main()
