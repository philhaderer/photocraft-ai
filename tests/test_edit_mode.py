"""Edit whole image: the whole picture goes in, a selection is ignored, a prompt is required, the edit workflows are valid.

    python tests/test_edit_mode.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pccomfy import bridge, workflows  # noqa: E402
from pccomfy.bridge import BridgeError, Request  # noqa: E402
import test_reference_mode as T  # noqa: E402

WFS = ("fibo2-edit.json", "qwen-image-21-edit.json", "flux2-klein-edit.json", "flux3-klein-edit.json")


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def run(wf, prompt="make it night", with_sel=True):
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp, with_sel=with_sel)
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(ROOT / "workflows" / wf), preset="X", run_no=1)
    req.params = workflows.GenParams(prompt=prompt, seed=5)
    return pc, b.run(req)


def main():
    for wf in WFS:
        tpl = workflows.load_template(ROOT / "workflows" / wf)
        assert links_ok(tpl) and not bridge.mask_is_used(tpl), wf
        g, out = workflows.apply_template(tpl, workflows.GenParams(prompt="make it night", seed=3, width=1024, height=768, batch=2), "pic.png", None)
        assert links_ok(g) and g[out]["class_type"] == "PreviewImage", wf
        for with_sel in (True, False):   # a selection changes nothing
            pc, res = run(wf, with_sel=with_sel)
            assert res["layers"] and res["region"] == {"x": 0, "y": 0, "w": T.W, "h": T.H}, (wf, res["region"])
    t2i = workflows.load_template(ROOT / "workflows" / "flux3-klein-t2i.json")   # Flux 3 text to image: a latent of its own
    assert links_ok(t2i) and not bridge.mask_is_used(t2i)
    g, out = workflows.apply_template(t2i, workflows.GenParams(prompt="a fox", seed=3, width=1536, height=1024, batch=2), None, None)
    lat = next(n for n in g.values() if n["class_type"] == "EmptyFlux2LatentImage")["inputs"]
    assert links_ok(g) and (lat["width"], lat["height"], lat["batch_size"]) == (1536, 1024, 2) and g[out]["class_type"] == "PreviewImage"
    try:
        run("qwen-image-21-edit.json", prompt="")
        raise AssertionError("empty prompt accepted")
    except BridgeError as e:
        assert "Describe the edit" in str(e)
    try:   # a mask-based workflow is no editor
        run("moss-image-inpaint.json")
        raise AssertionError("mask workflow accepted")
    except BridgeError as e:
        assert "edit workflow" in str(e)
    # the whole canvas selected in Generative fill = a fresh picture from the text: no red outline frame in the picture
    from PIL import Image
    import numpy as np
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp, with_sel=True)
    pc.docs[0].sel = Image.new("L", (T.W, T.H), 255)
    b.comfy = T.FakeComfy()
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / "qwen-image-21-edit.json"), preset="X", run_no=1)
    req.params = workflows.GenParams(prompt="a snowy mountain", seed=5)
    b.run(req)
    sent_prompt = b.comfy.graphs[0]["8"]["inputs"]["prompt"]
    assert sent_prompt.endswith("a snowy mountain") and "outline" not in sent_prompt.lower() and "red" not in sent_prompt.lower(), sent_prompt
    # a part selected (not the whole picture) still gets the marked fill
    pc, _, b2 = T.make(tempfile.mkdtemp(), with_sel=True)
    b2.comfy = T.FakeComfy()
    b2.run(req)
    assert "outline" in b2.comfy.graphs[0]["8"]["inputs"]["prompt"].lower() or "red" in b2.comfy.graphs[0]["8"]["inputs"]["prompt"].lower()
    # Edit whole image with a part selected: the selection becomes the whole canvas
    pc, res = run("qwen-image-21-edit.json", with_sel=True)
    assert any(c == "select.all" for c, _ in pc.log), "selection not widened to the whole picture"
    print("ALL OK (edit mode)")


if __name__ == "__main__":
    main()
