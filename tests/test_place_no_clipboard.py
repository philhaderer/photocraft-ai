"""The result goes into PhotoCraft without its clipboard (layer.copyToDocument): what the user copied stays there.

Checks against the PhotoCraft simulator (behaviour measured in 0.15.1 and 0.16): the layer lands exactly on the region,
the soft layer mask is the computed mask to the grey value, the user's selection is the same before and after (soft,
hard and no layer mask, one and several variants), the helper files are closed and the user's picture stays open.

    python tests/test_place_no_clipboard.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import test_reference_mode as T  # noqa: E402
from pccomfy import imaging, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

CLIP = object()   # what the user copied before the run


def comfy(variants: int):
    c = T.FakeComfy()
    c.output_images = lambda hist, node_id=None: [Image.new("RGB", (64, 64), (10, 200 - 40 * k, 10)) for k in range(variants)]
    return c


def fill_run(layer_mask: str, variants: int = 1, wf: str = "krea2-turbo-inpaint.json"):
    pc, _, b = T.make(tempfile.mkdtemp())
    pc.clip = CLIP
    b.comfy = comfy(variants)
    sel_before = np.asarray(pc.docs[0].sel).copy()
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / wf), layer_mask=layer_mask, variants=variants,
                  preset="X", run_no=1)
    req.params = workflows.GenParams(prompt="a red ball", seed=3)
    res = b.run(req)
    return pc, res, sel_before


def main():
    for lm in ("soft", "selection", "none"):
        for variants in (1, 3):
            pc, res, sel_before = fill_run(lm, variants)
            cmds = [c for c, _ in pc.log]
            assert pc.clip is CLIP, "the clipboard was touched"
            assert not any(c in ("edit.copy", "edit.paste", "edit.pasteSpecial.pasteInto") for c in cmds), cmds
            assert len(pc.docs) == 1 and pc.docs[0].name == "scene.png" and pc.active == 0, [d.name for d in pc.docs]
            d = pc.docs[0]
            assert d.sel is not None and np.array_equal(np.asarray(d.sel), sel_before), (lm, variants, "selection changed")
            assert not d.channels, "the saved selection channel was left behind"
            assert not any(l.get("name", "").startswith("pccomfy-") for l in d.layers)
            placed = [l for l in d.layers if l["id"] in res["layers"]]
            assert len(placed) == len(res["layers"]) == variants, (lm, variants, res["layers"])
            assert all((l.get("mask") is not None) == (lm != "none") for l in placed), lm
            # only the first variant is visible, it is the top layer
            assert d.layers[-1]["id"] == res["layers"][0] and d.layers[-1]["visible"]
            assert all(not l["visible"] for l in placed if l["id"] != res["layers"][0])

    # exact placement: the result's pixels sit on the region (green inside, nothing outside it)
    pc, res, _ = fill_run("none")
    lay = next(l for l in pc.docs[0].layers if l["id"] == res["layers"][0])
    a = np.asarray(lay["img"].getchannel("A"))
    ys, xs = np.nonzero(a)
    r = res["region"]
    assert (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) == (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]), (r, xs.min(), ys.min())

    # soft mask: the layer's mask is exactly the mask the bridge computed (grow/blur of the selection), placed on the region
    pc, res, sel_before = fill_run("soft")
    lay = next(l for l in pc.docs[0].layers if l["id"] == res["layers"][0])
    r = res["region"]
    box = imaging.Box(r["x"], r["y"], r["w"], r["h"])
    want = imaging.prepare_mask(Image.fromarray(sel_before).crop(box.pil()), 8, 8)
    got = np.asarray(lay["mask"])[box.y:box.y + box.h, box.x:box.x + box.w]
    assert np.abs(got.astype(int) - np.asarray(want).astype(int)).max() == 0
    outside = np.asarray(lay["mask"]).copy()
    outside[box.y:box.y + box.h, box.x:box.x + box.w] = 0
    assert outside.max() == 0

    # a broken copy must not leave the user's picture closed or the selection lost
    pc, _, b = T.make(tempfile.mkdtemp())
    b.comfy = comfy(2)
    sel_before = np.asarray(pc.docs[0].sel).copy()
    real = pc.execute
    def broken(cmd, params=None):
        if cmd == "layer.copyToDocument" and any(c == "select.loadSelection" for c, _ in pc.log):
            from pccomfy.photocraft import PhotoCraftError
            raise PhotoCraftError("layer.copyToDocument: test failure")
        return real(cmd, params)
    pc.execute = broken
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / "krea2-turbo-inpaint.json"), layer_mask="soft",
                  variants=2, preset="X", run_no=1)
    req.params = workflows.GenParams(prompt="a red ball", seed=3)
    try:
        b.run(req)
    except Exception as e:
        assert "test failure" in str(e), e
    else:
        raise AssertionError("the broken copy was not reached")
    assert pc.docs[0].name == "scene.png" and len(pc.docs) == 1, [d.name for d in pc.docs]
    assert np.array_equal(np.asarray(pc.docs[0].sel), sel_before) and not pc.docs[0].channels
    print("ok")


if __name__ == "__main__":
    main()
