"""Qwen 2.1 Upscale (workflow qwen212KUpscale_v10 as an API graph): the picture, the result's size, the prompt and the seed reach
the right nodes; no LoRA and no upscaler node; Qwen offers the function.

    python tests/test_qwen_upscale.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import inventory, manifest, models, workflows  # noqa: E402
from pccomfy.workflows import GenParams  # noqa: E402

WF = ROOT / "workflows" / "qwen-image-21-upscale.json"


def main():
    g = json.loads(WF.read_text(encoding="utf-8"))
    assert all(str(v[0]) in g for n in g.values() for v in n["inputs"].values() if isinstance(v, list))
    assert workflows.has_upscale_slot(g) and not workflows.lora_subgraph(g) and workflows.lora_strength(g) is None
    assert not any("Upscale" in n["class_type"] and n["class_type"] != "ImageScaleToTotalPixels" for n in g.values())
    p = GenParams(prompt="", seed=7)
    p.extra["megapixels"] = 4.2
    out, node = workflows.apply_template(g, p, "in.png", None)
    assert out["6"]["inputs"]["image"] == "in.png" and out["13"]["inputs"]["megapixels"] == 4.2 and out["10"]["inputs"]["seed"] == 7
    assert out["8"]["inputs"]["prompt"] == models.QWEN_UPSCALE_DEFAULT and node == "12"
    assert out["9"]["inputs"]["width"] == ["14", 0]            # the latent takes the size of the enlarged picture, not a typed one
    p.prompt = "a portrait with fine skin detail"
    assert workflows.apply_template(g, p, "in.png", None)[0]["8"]["inputs"]["prompt"] == p.prompt          # typed text replaces it
    mode = models.BY_KEY["qwen"].modes["upscale"]
    assert mode.workflow == WF.name and mode.settings["turbo"] is False and mode.prompt_hint == models.QWEN_UPSCALE_DEFAULT
    assert mode.prompts == ()                                    # no Default / Detailed switches (user 2.11.)
    refine = models.BY_KEY["qwen"].modes["refine"]               # the same graph at the canvas size, waits for the user's test
    assert refine.workflow == WF.name and refine.prompt_hint == models.QWEN_UPSCALE_DEFAULT and refine.prompts == ()
    assert models.RANKING["upscale"][0] == "qwen" and models.ranking_text("refine").endswith("(not ranked: Qwen).")
    assert inventory.mode_files("qwen", "refine") == manifest.mode_required("qwen", "refine")
    assert inventory.mode_files("qwen", "upscale") == manifest.mode_required("qwen", "upscale")      # no switch brings extra files
    print("ALL OK (qwen upscale)")


if __name__ == "__main__":
    main()
