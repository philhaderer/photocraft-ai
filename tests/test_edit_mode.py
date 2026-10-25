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

WFS = ("fibo2-edit-plain.json", "qwen-image-21-edit.json", "flux2-klein-edit.json", "flux3-klein-edit.json")


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
    print("ALL OK (edit mode)")


if __name__ == "__main__":
    main()
