"""Upscale (new file) and Refine (same size): the whole bridge run against the PhotoCraft simulator and a fake ComfyUI.

The picture goes to the workflow at its own size; a node titled pc:upscale gets the result's megapixels. Upscale opens
the result as a new document (the original is not touched), Refine puts it on a new layer.

    python tests/test_upscale_mode.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from pccomfy import bridge, workflows  # noqa: E402
from pccomfy.bridge import Bridge, BridgeError, Request  # noqa: E402
import test_reference_mode as T  # noqa: E402  (the PhotoCraft simulator and the fake ComfyUI)

WF = ROOT / "workflows" / "flux3-klein-upscale.json"


def links_resolve(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def run(mode, wf=WF, scale=2.0, prompt="", with_sel=False):
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp, with_sel=with_sel, layers=2)
    b.comfy = T.FakeComfy()
    req = Request(mode=mode, workflow=str(wf) if wf else None, scale=scale)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    res = b.run(req)
    return pc, b, res


def mp_of(b):
    g = b.comfy.graphs[0]
    return [n["inputs"]["megapixels"] for n in g.values() if n.get("_meta", {}).get("title", "").startswith("pc:upscale")][0]


def expect_error(text, *a, **kw):
    try:
        run(*a, **kw)
    except BridgeError as e:
        assert text in str(e), (text, str(e))
        return
    raise AssertionError(f"expected BridgeError containing {text!r}")


def main():
    # the workflow itself
    tpl = workflows.load_template(WF)
    assert links_resolve(tpl) and workflows.has_upscale_slot(tpl) and not workflows.has_upscale_slot(
        workflows.load_template(ROOT / "workflows" / "fibo2-edit-plain.json"))
    assert not bridge.prompt_phase_nodes(tpl) and not workflows.prompt_writers(tpl)   # the description is plain text
    ti = {n["class_type"] for n in tpl.values()}
    assert "SaveImage" not in ti and "AUSBOSS_NODES_SaveImage" not in ti and "PreviewImage" in ti
    ref = tpl["161"]["inputs"]
    assert ref["images.image0"] == ["154", 0] and tpl["165"]["inputs"]["stitcher"] == ["154", 1]   # the tiles and the stitcher
    p = workflows.GenParams(prompt="a young woman", seed=5)
    p.extra["megapixels"] = 3.5
    g, out = workflows.apply_template(tpl, p, "pic.png", None)
    assert g["2"]["inputs"]["image"] == "pic.png" and g["3"]["inputs"]["megapixels"] == 3.5
    assert g["154"]["inputs"]["megapixels"] == 0                       # the inner tiling stays as saved
    assert g["24"]["inputs"]["text"] == "a young woman" and g["5"]["inputs"]["seed"] == 5
    assert g[out]["class_type"] == "PreviewImage"

    # Upscale: a new document, the original stays as it was
    pc, b, res = run("upscale", scale=2.0, prompt="a young woman")
    assert len(pc.docs) == 2 and pc.active == 1, [d.name for d in pc.docs]
    assert pc.docs[1].name == "scene upscaled 64x64.png", pc.docs[1].name     # the fake model returns 64x64
    assert len(pc.docs[0].layers) == 2, "the original document must not get a layer"
    assert not any(c == "history.newSnapshot" for c, _ in pc.log)
    assert abs(mp_of(b) - 200 * 120 * 4 / 1e6) < 1e-6, mp_of(b)
    img_up = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
    assert img_up.size == (200, 120), img_up.size                          # at its own size, not scaled to a base resolution
    assert b.comfy.graphs[0]["24"]["inputs"]["text"] == "a young woman" and res["documents"] == 1

    # Upscale of a selection: only that part, at its own size
    pc, b, _ = run("upscale", scale=3.0, with_sel=True)
    img_up = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
    assert img_up.size == (T.SEL[2] - T.SEL[0], T.SEL[3] - T.SEL[1]), img_up.size
    assert abs(mp_of(b) - 80 * 60 * 9 / 1e6) < 1e-6

    # Refine: factor 1, the result is a layer in the same document
    pc, b, res = run("refine", scale=4.0)       # the factor is ignored
    assert len(pc.docs) == 1 and res["layers"] and abs(mp_of(b) - 200 * 120 / 1e6) < 1e-6
    assert any(c == "history.newSnapshot" for c, _ in pc.log)          # a layer was added: one click back is kept

    # errors with a clear message
    expect_error("pc:upscale", "upscale", wf=ROOT / "workflows" / "fibo2-edit-plain.json")
    expect_error("pc:upscale", "refine", wf=None)
    expect_error("between 1 and 8", "upscale", scale=9)
    bridge.MAX_RESULT_MP = 1.0                                         # 200x120 at 8x = 1.5 megapixels
    try:
        expect_error("limit is 1", "upscale", scale=8)
    finally:
        bridge.MAX_RESULT_MP = 24.0
    print("ALL OK (upscale/refine)")


if __name__ == "__main__":
    main()
