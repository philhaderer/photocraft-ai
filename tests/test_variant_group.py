"""Several variants go into one layer group ("Fill Selection 3"); one result stays a loose layer.

The group keeps the order (#1 on top) and the visibility (#1 shown, the others hidden), #1 is the active layer, the
next run lands above the group (not in it), and a refused grouping leaves the layers loose as before.

    python tests/test_variant_group.py
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import test_reference_mode as T  # noqa: E402
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Bridge, Request  # noqa: E402
from pccomfy.photocraft import PhotoCraftError  # noqa: E402


def comfy(variants: int):
    c = T.FakeComfy()
    c.output_images = lambda hist, node_id=None: [Image.new("RGB", (64, 64), (10, 200 - 40 * k, 10)) for k in range(variants)]
    return c


def run(b, variants, group_name="Fill Selection 3", mode="inpaint", layer_mask="auto"):
    b.comfy = comfy(variants)
    req = Request(mode=mode, workflow=str(ROOT / "workflows" / "krea2-turbo-inpaint.json"), variants=variants, layer_mask=layer_mask,
                  preset="Krea 2 Fill Selection", run_no=3, group_name=group_name)
    req.params = workflows.GenParams(prompt="a red ball", seed=3)
    return b.run(req)


def main():
    pc, _, b = T.make(tempfile.mkdtemp())
    n_before = len(pc.docs[0].layers)
    res = run(b, 3)
    d = pc.docs[0]
    g = d.layers[-1]
    assert res["group"] == g["id"] and g["name"] == "Fill Selection 3" and g["visible"], g.get("name")
    assert len(d.layers) == n_before + 1, "the variants are not all in the group"
    assert [m["id"] for m in reversed(g["members"])] == res["layers"], "order changed (#1 must be on top)"
    assert [m["visible"] for m in reversed(g["members"])] == [True, False, False]
    assert [m["name"] for m in reversed(g["members"])] == ["Krea 2 Fill Selection #3.1", "Krea 2 Fill Selection #3.2",
                                                           "Krea 2 Fill Selection #3.3"]
    assert d.active == res["layers"][0], "#1 is not the active layer"

    # the next run (one result) lands on top of the stack, not inside the group
    res2 = run(b, 1, group_name="Fill Selection 4")
    assert res2["group"] is None and d.layers[-1]["id"] == res2["layers"][0]
    assert len(g["members"]) == 3
    # also with the hard mask (placed above the ACTIVE layer, which is #1 inside the group after a run with variants)
    for lm in ("selection", "soft", "none"):
        pc, _, b = T.make(tempfile.mkdtemp())
        run(b, 2, layer_mask=lm)
        g = pc.docs[0].layers[-1]
        b = Bridge(pc, T.FakeComfy(), b.exchange)    # the plugin was restarted in between
        res2 = run(b, 1, group_name="Fill Selection 4", layer_mask=lm)
        assert pc.docs[0].layers[-1]["id"] == res2["layers"][0] and len(g["members"]) == 2, (lm, "went into the group")

    # without a name from the window (command line): a plain name
    pc, _, b = T.make(tempfile.mkdtemp())
    run(b, 2, group_name="")
    assert pc.docs[0].layers[-1]["name"] == "AI inpaint variants"

    # PhotoCraft refuses the group: the layers stay loose and the run still succeeds
    pc, _, b = T.make(tempfile.mkdtemp())
    real = pc.execute
    def refuse(cmd, params=None):
        if cmd == "layer.new.groupFromLayers":
            raise PhotoCraftError("layer.new.groupFromLayers: test refusal")
        return real(cmd, params)
    pc.execute = refuse
    res = run(b, 2)
    assert res["group"] is None and [l["id"] for l in pc.docs[0].layers[-2:]] == res["layers"][::-1]
    assert pc.docs[0].active == res["layers"][0]
    print("ok")


if __name__ == "__main__":
    main()
