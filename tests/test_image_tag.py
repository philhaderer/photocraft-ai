"""The picture tag a workflow names for its model ("<image1>" for Qwen Image 2.1) goes in front of the typed prompt.

    python tests/test_image_tag.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge, imaging, workflows  # noqa: E402

WF = ROOT / "workflows"


def node(tag=None):
    n = {"class_type": "X", "inputs": {}}
    if tag:
        n["_meta"] = {"pc_image_tag": tag}
    return n


def tagged_template():
    """A minimal editor workflow: a picture, a mask slot and an encoder that names its picture <image1>."""
    return {"1": {"class_type": "LoadImage", "inputs": {"image": "x.png"}, "_meta": {"title": "pc:image"}},
            "2": {"class_type": "LoadImage", "inputs": {"image": "x.png"}, "_meta": {"title": "pc:mask"}},
            "3": {"class_type": "TextEncodeQwenImage21", "inputs": {"prompt": "", "images.image_1": ["1", 0]},
                  "_meta": {"title": "pc:prompt", "pc_image_tag": "<image1>"}}}


def main():
    n = node("<image1>")
    assert workflows.with_image_tag("make it night", n) == "<image1> make it night"
    assert workflows.with_image_tag("  make it night ", n) == "<image1> make it night"
    # typed by hand already (any case): not doubled
    assert workflows.with_image_tag("in <Image1> make it night", n) == "in <Image1> make it night"
    # no text: nothing to tag; no tag named: untouched
    assert workflows.with_image_tag("", n) == "" and workflows.with_image_tag("   ", n) == "   "
    assert workflows.with_image_tag("make it night", node()) == "make it night"

    p = workflows.GenParams(prompt="make it night")
    g, _ = workflows.apply_template(tagged_template(), p, "img.png", "mask.png")
    assert g["3"]["inputs"]["prompt"] == "<image1> make it night", g["3"]["inputs"]["prompt"]

    # the instruction the bridge builds for an outpaint gets the tag as well
    keep = imaging.Box(0, 100, 800, 600)
    text = bridge.outpaint_prompt("a landscape in upper austria", True, keep, (800, 800))
    g, _ = workflows.apply_template(tagged_template(), workflows.GenParams(prompt=text), "img.png", "mask.png")
    assert g["3"]["inputs"]["prompt"].startswith("<image1> a landscape in upper austria, replace white"), g["3"]["inputs"]["prompt"]

    # Fibo workflows name no tag: their prompts are exactly what they were
    for name in ("fibo2-edit-plain.json", "fibo2-edit-vgl-qwen35-convrot.json"):
        g, _ = workflows.apply_template(workflows.load_template(WF / name), p, "img.png", "mask.png")
        texts = [v["inputs"].get("prompt", v["inputs"].get("text", v["inputs"].get("instruction")))
                 for v in g.values() if "prompt" in workflows._tags(v)]
        assert texts and all(t == "make it night" for t in texts), (name, texts)
    print("ALL OK (image tag)")


if __name__ == "__main__":
    main()
