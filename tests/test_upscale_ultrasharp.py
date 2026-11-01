"""Flux 3 Upscale: the stage "4x UltraSharp" (for generated pictures) next to "SeedVR2 pre-cleaning", in both graphs.

    python tests/test_upscale_ultrasharp.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import inventory, manifest, models, workflows  # noqa: E402

FILE = "4x-UltraSharpV2.safetensors"


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def main():
    for name in ("flux3-klein-upscale.json", "flux3-klein-upscale-std.json"):
        g = json.loads((ROOT / "workflows" / name).read_text(encoding="utf-8"))
        info = workflows.stage_info(g)
        assert [s["label"] for s in info] == ["SeedVR2 pre-cleaning", "4x UltraSharp"], name
        assert [s["excludes"] for s in info] == [["12"], ["153"]] and not any(s["default_on"] for s in info)
        seed, ultra = "153", "12"
        both_off = workflows.bypass_stage(g, only=[seed, ultra])
        assert links_ok(both_off) and "12" not in both_off and "13" not in both_off and "152" not in both_off
        assert both_off["153"]["inputs"]["image"] == ["2", 0], name            # the plain way: the picture itself
        us = workflows.bypass_stage(g, only=[seed])
        assert links_ok(us) and us["153"]["inputs"]["image"] == ["13", 0] and "152" not in us
        assert us["13"]["inputs"]["image"] == ["2", 0] and us["12"]["inputs"]["model_name"] == FILE
        sv = workflows.bypass_stage(g, only=[ultra])
        assert links_ok(sv) and sv["153"]["inputs"]["image"] == ["152", 0] and "13" not in sv and "12" not in sv
    f = manifest.FILES[FILE]
    assert f.kind == "upscale_model" and f.sha256 and f.size and f.target.endswith("upscale_models") and "non-commercial" in f.note
    assert FILE in manifest.mode_optional("flux3", "upscale") and FILE not in manifest.mode_required("flux3", "upscale")
    assert FILE in inventory.default_switch_files("flux3", "upscale")      # the standard settings switch it on (user 2.11.): the file is needed
    assert FILE in inventory.mode_files("flux3", "upscale")
    assert models.BY_KEY["flux3"].modes["upscale"].settings["stage2_on"] is True and not models.BY_KEY["flux3"].modes["upscale"].settings["stage_on"]
    print("ALL OK (upscale ultrasharp)")


if __name__ == "__main__":
    main()
