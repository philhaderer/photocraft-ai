"""Fill with Qwen asks for the full size of the outline; Fibo keeps its wording (stubbed PhotoCraft and ComfyUI).

Test round 28.10.: with "scaled to fit it" Qwen drew the object small, far inside the outline; Fibo filled it.

    python tests/test_qwen_fill_wording.py
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as t  # noqa: E402

from pccomfy import bridge, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

ROOT = t.ROOT


def sent_prompt(wf, prompt="a boat"):
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, layers=2)
    b.comfy = t.FakeComfy()
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / wf), enhance=False)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    b.run(req)
    g = b.comfy.graphs[0]
    node = next(n for n in g.values() if n["class_type"] in ("TextEncodeQwenImage21", "TextEncodeFibo2"))
    return node["inputs"]["prompt"]


def main():
    rect = Image.new("L", (100, 80), 255)
    assert bridge.fill_prompt("a boat.", rect) == bridge.FILL_PROMPT.format(text="a boat", shape="rectangle")
    assert bridge.fill_prompt("a boat", rect, "C:/x/qwen-image-21-edit.json").startswith(
        "a boat. Make it as large as the red rectangle, filling it from edge to edge")
    assert bridge.fill_prompt("a boat", rect, "C:/x/fibo2-edit.json") == bridge.FILL_PROMPT.format(text="a boat", shape="rectangle")
    # through a whole run: Qwen gets the large wording, Fibo the old one
    q = sent_prompt("qwen-image-21-edit.json")
    assert "as large as the red" in q and "scaled to fit" not in q, q
    f = sent_prompt("fibo2-edit.json")
    assert "scaled to fit" in f and "as large as" not in f, f
    print("ALL OK (qwen fill wording)")


if __name__ == "__main__":
    main()
