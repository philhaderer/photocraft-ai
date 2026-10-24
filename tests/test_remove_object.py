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


def run(wf, prompt="", enhance=True, mode="inpaint", **kw):
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, layers=2)
    b.comfy = t.FakeComfy()
    req = Request(mode=mode, workflow=str(ROOT / "workflows" / wf), enhance=enhance, **kw)
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

    # Generative fill without text and an instruction editor: a clear error (Remove is for taking things away)
    for wf in ("fibo2-edit-plain.json", "fibo2-edit-vgl-bionic-qwen35-9b.json"):
        try:
            run(wf)
        except BridgeError as e:
            assert "needs a text" in str(e) and "Remove" in str(e)
        else:
            raise AssertionError("expected error")

    # Remove object: the removal instruction, text model bypassed even with enhance on, no "type an instruction" error
    b, _ = run("fibo2-edit-vgl-bionic-qwen35-9b.json", enhance=True, mode="remove")
    assert prompt_of(b.comfy.graphs[0]) == bridge.REMOVE_PROMPT.format(shape="rectangle")

    # Remove object tries again (new seed) while the area is unchanged, and stops when it worked
    class Unchanged(t.FakeComfy):
        def __init__(self, ok_on):
            super().__init__()
            self.ok_on = ok_on

        def output_images(self, hist, node_id=None):
            if len(self.graphs) >= self.ok_on:
                return [Image.new("RGB", (64, 64), (10, 200, 10))]
            return [next(v for k, v in self.uploads.items() if k.endswith("-image.png")).copy()]   # as sent: unchanged

    for ok_on, expect in ((9, 3), (2, 2), (1, 1)):
        tmp = tempfile.mkdtemp()
        pc, _, b = t.make(tmp, layers=2)
        b.comfy = Unchanged(ok_on)
        req = Request(mode="remove", workflow=str(ROOT / "workflows" / "fibo2-edit-plain.json"), enhance=False)
        req.params = workflows.GenParams(prompt="", seed=7)
        b.run(req)
        seeds = [next(n["inputs"]["seed"] for n in g.values() if n["class_type"] == "KSampler") for g in b.comfy.graphs]
        assert len(b.comfy.graphs) == expect and len(set(seeds)) == expect, (ok_on, expect, seeds)
        prompts = [prompt_of(g) for g in b.comfy.graphs]
        want = [bridge.REMOVE_PROMPT, bridge.REMOVE_PROMPT_ALT, bridge.REMOVE_PROMPT][:expect]
        assert prompts == [w.format(shape="rectangle") for w in want], prompts   # the tries alternate the wording

    # removal_done: unchanged / outline left = not done; area replaced = done
    before = Image.new("RGB", (200, 200), (40, 90, 40))
    mk = Image.new("L", (200, 200), 0)
    mk.paste(255, (50, 50, 150, 150))
    assert not imaging.removal_done(before, before, mk, 4)
    assert not imaging.removal_done(before, imaging.mark_outline(before, mk, 4), mk, 4)
    changed = before.copy()
    changed.paste((200, 200, 200), (50, 50, 150, 150))
    assert imaging.removal_done(before, changed, mk, 4)
    assert imaging.removal_score(before, before, mk, 4) == 0 and imaging.removal_score(before, changed, mk, 4) > 0.9
    # a half-removed figure (live test: 0.11) is not "done", a removed small object (0.16) is
    half = before.copy()
    half.paste((200, 200, 200), (50, 50, 80, 80))     # ~10 % of the selection changed
    assert not imaging.removal_done(before, half, mk, 4)

    # Remove object with a workflow that uses the mask: clear error
    try:
        tmp = tempfile.mkdtemp()
        pc, _, b = t.make(tmp, layers=2)
        b.comfy = t.FakeComfy()
        req = Request(mode="remove", workflow=None, enhance=False)
        req.params = workflows.GenParams(prompt="", seed=7)
        b.run(req)
    except BridgeError as e:
        assert "Fibo workflow" in str(e)
    else:
        raise AssertionError("expected error")

    # a round selection says "outline"
    mm = Image.new("L", (100, 100), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(mm).ellipse((10, 10, 90, 90), fill=255)
    assert "red outline" in bridge.remove_prompt(mm) and "red rectangle" in bridge.remove_prompt(Image.new("L", (50, 50), 255))

    # typed text (Generative fill): the selection is marked in the picture and the text is wrapped, one pass
    b, _ = run("fibo2-edit-plain.json", prompt="a red car")
    img = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
    pr = prompt_of(b.comfy.graphs[0])
    assert red(img) > 0 and len(b.comfy.graphs) == 1
    assert pr.startswith("a red car. Place it only inside the red ") and "Also remove the red" in pr

    # with a text-model workflow: Enhance on = the wrapped text goes to the text model as its instruction (no placement
    # hint on top), Enhance off = straight to Fibo
    b, _ = run("fibo2-edit-vgl-bionic-qwen35-9b.json", prompt="a red car", enhance=True)
    g = b.comfy.graphs[0]
    vgl = next(n for n in g.values() if n["class_type"] == "VGLBionicEditPrompt")
    assert vgl["inputs"]["instruction"].startswith("a red car. Place it only inside the red ") and "Apply this only" not in vgl["inputs"]["instruction"]
    b, _ = run("fibo2-edit-vgl-bionic-qwen35-9b.json", prompt="a red car", enhance=False)
    g = b.comfy.graphs[0]
    assert not any(n["class_type"] == "VGLBionicEditPrompt" for n in g.values())
    assert prompt_of(g).startswith("a red car. Place it only inside the red ")

    print("ALL OK (remove object)")


if __name__ == "__main__":
    main()
