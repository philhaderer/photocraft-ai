"""Qwen text to image (a blank canvas goes in as the picture), the Flux 3 text-to-image prompt upsampler, no "select.deselect"
without a selection.

    python tests/test_round_bridge.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pccomfy import bridge, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
import test_reference_mode as T  # noqa: E402


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def main():
    # Qwen 2.1 as text to image: no selection needed, a white canvas of the result's size is the picture
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="txt2img", workflow=str(ROOT / "workflows" / "qwen-image-21-edit.json"), preset="X", run_no=1, base_res=1024)
    req.params = workflows.GenParams(prompt="a red fox in the snow", seed=5)
    res = b.run(req)
    assert res["layers"]
    g = b.comfy.graphs[0]
    img = next(n for n in g.values() if "image" in str(n.get("_meta", {}).get("title", "")) and n["class_type"] == "LoadImage")
    assert img["inputs"]["image"] != "example.png" and any(im.getpixel((3, 3)) == (255, 255, 255) for im in b.comfy.uploads.values())
    assert g["8"]["inputs"]["prompt"].endswith("a red fox in the snow") and "red" not in g["8"]["inputs"]["prompt"].replace("a red fox", "")

    # Flux 3 text to image: the prompt upsampler is part of the workflow; switched off, the typed prompt goes straight in
    t2i = workflows.load_template(ROOT / "workflows" / "flux3-klein-t2i.json")
    assert links_ok(t2i) and workflows.writer_name(t2i) == "Qwen 3.5 9B" and bridge.has_tag(t2i, "prompt")
    on, _ = workflows.apply_template(t2i, workflows.GenParams(prompt="a fox", seed=3, width=1536, height=1024), None, None)
    assert any(n["class_type"] == "TextGenerate" and n["inputs"]["prompt"] == "a fox" for n in on.values()) and links_ok(on)
    off, _ = workflows.apply_template(workflows.bypass_prompt_writer(t2i, "a fox"), workflows.GenParams(prompt="a fox", seed=3, width=1536, height=1024), None, None)
    assert not any(n["class_type"] == "TextGenerate" for n in off.values()) and links_ok(off)
    assert next(n for n in off.values() if n["class_type"] == "CLIPTextEncode")["inputs"]["text"] == "a fox"
    assert workflows.writer_name(workflows.load_template(ROOT / "workflows" / "moss-image-t2i.json")) == "Qwen 3.5 9B"
    assert workflows.writer_name(workflows.load_template(ROOT / "workflows" / "fibo2-edit-plain.json")) == ""
    print("ALL OK (round bridge)")


if __name__ == "__main__":
    main()
