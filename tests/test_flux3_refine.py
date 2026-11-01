"""Flux 3 Refine (after Pixaroma's "Restore and Colorize"): standard nodes only, size of the picture, prompt switch.

    python tests/test_flux3_refine.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

WF = ROOT / "workflows" / "flux3-klein-refine.json"


def main():
    g = json.loads(WF.read_text(encoding="utf-8"))
    assert not any("AUSBOSS" in n["class_type"] or "Pixaroma" in n["class_type"] for n in g.values())   # standard nodes only
    assert all(str(v[0]) in g for n in g.values() for v in n["inputs"].values() if isinstance(v, list))
    assert workflows.has_upscale_slot(g) and workflows.lora_strength(g) is None   # sets the size, no LoRA
    assert g["163"]["inputs"]["steps"] == 16 and g["163"]["inputs"]["cfg"] == 1 and g["161"]["inputs"]["resolution"] == "keep resolution"

    m = models.FLUX3.modes["refine"]
    assert m.workflow == WF.name and [p[0] for p in m.prompts] == ["Default", "Restore"]
    assert m.prompts[0][1] == models.FLUX3_DEFAULT and models.FLUX3_RESTORE in models.STOCK_PROMPTS
    assert "flux3" in models.RANKING["refine"]

    for typed, want in (("", models.FLUX3_DEFAULT), (models.FLUX3_RESTORE, models.FLUX3_RESTORE)):
        pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
        b.comfy = T.FakeComfy()
        req = Request(mode="refine", workflow=str(WF), preset="X", run_no=1, scale=1.0)
        req.params = workflows.GenParams(prompt=typed, seed=5)
        b.run(req)
        out = b.comfy.graphs[0]
        assert out["159"]["inputs"]["text"] == want
        mp = out["3"]["inputs"]["megapixels"]                      # the picture's own size, not a fixed 1 MP
        assert abs(mp - T.W * T.H / 1e6) < 0.01, mp
    # a selection is ignored: the whole picture goes in (1.11., user: Refine only without a selection)
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=True)
    b.comfy = T.FakeComfy()
    req = Request(mode="refine", workflow=str(WF), preset="X", run_no=1, scale=1.0)
    req.params = workflows.GenParams(prompt="", seed=5)
    res = b.run(req)
    assert res["region"] == {"x": 0, "y": 0, "w": T.W, "h": T.H}, res["region"]
    print("ALL OK (flux3 refine)")


if __name__ == "__main__":
    main()
