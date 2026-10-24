"""Fill with an empty instruction (Fibo) = remove the object the selection outlines (red outline in the picture).

    python tests/test_remove_object.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as t  # noqa: E402

from pccomfy import bridge, imaging, workflows  # noqa: E402
from pccomfy.bridge import BridgeError, Request  # noqa: E402

ROOT = t.ROOT


def red(im):
    a = np.asarray(im.convert("RGB")).astype(int)
    return int(((a[..., 0] > 240) & (a[..., 1] < 20) & (a[..., 2] < 20)).sum())


def run(wf, prompt="", enhance=True, empty_removes=True):
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, layers=2)
    b.comfy = t.FakeComfy()
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / wf), enhance=enhance, empty_removes=empty_removes)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    return b, b.run(req)


def prompt_of(graph):
    return next(n["inputs"]["prompt"] for n in graph.values() if n["class_type"] == "TextEncodeFibo2")


def main():
    # outline drawing: thin red ring around the mask, nothing inside, nothing far outside
    base = Image.new("RGB", (100, 100), (30, 60, 200))
    m = Image.new("L", (100, 100), 0)
    m.paste(255, (30, 30, 70, 70))
    out = imaging.mark_outline(base, m, 2)
    assert out.getpixel((30, 50)) == (255, 0, 0) and out.getpixel((50, 50)) == (30, 60, 200) and out.getpixel((5, 5)) == (30, 60, 200)
    assert red(out) < 40 * 4 * 5 + 200

    # empty prompt, plain Fibo workflow: outline in the picture, fixed removal prompt, one image only
    b, res = run("fibo2-edit-plain.json")
    img = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
    assert red(img) > 50
    g = b.comfy.graphs[0]
    assert prompt_of(g) == bridge.REMOVE_PROMPT.format(shape="rectangle")
    assert not [k for k in b.comfy.uploads if k.endswith("-ref.png")]

    # empty prompt with a text-model workflow and enhance on: no "type an instruction" error, text model bypassed
    b, _ = run("fibo2-edit-vgl-bionic-qwen35-9b.json", enhance=True)
    g = b.comfy.graphs[0]
    assert prompt_of(g) == bridge.REMOVE_PROMPT.format(shape="rectangle")

    # a round selection says "outline"
    mm = Image.new("L", (100, 100), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(mm).ellipse((10, 10, 90, 90), fill=255)
    assert "red outline" in bridge.remove_prompt(mm) and "red rectangle" in bridge.remove_prompt(Image.new("L", (50, 50), 255))

    # typed text: normal fill, no outline
    b, _ = run("fibo2-edit-plain.json", prompt="a red car")
    img = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
    assert red(img) == 0 and prompt_of(b.comfy.graphs[0]).startswith("a red car")

    # switched off: old behaviour with a text-model workflow (error)
    try:
        run("fibo2-edit-vgl-bionic-qwen35-9b.json", enhance=True, empty_removes=False)
    except BridgeError as e:
        assert "Type an instruction" in str(e)
    else:
        raise AssertionError("expected error")
    print("ALL OK (remove object)")


if __name__ == "__main__":
    main()
