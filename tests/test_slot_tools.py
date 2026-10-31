"""Tools of a reference slot: cut-out of the background and a description by Qwen 3.5 9B: birefnet-remove-bg.json (ComfyUI's own BiRefNet nodes) and Bridge.remove_background.

    python tests/test_slot_tools.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402
from pccomfy import bridge, workflows  # noqa: E402
import test_reference_mode as T  # noqa: E402


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


class CutComfy(T.FakeComfy):
    def output_images(self, hist, node_id=None):
        self.out_node = node_id
        return [Image.new("RGBA", (40, 30), (255, 0, 0, 0))]


def main():
    tpl = workflows.load_template(workflows.BIREFNET_WORKFLOW)
    assert links_ok(tpl) and bridge.has_tag(tpl, "image") and bridge.has_tag(tpl, "output")
    kinds = {n["class_type"] for n in tpl.values()}
    assert {"LoadBackgroundRemovalModel", "RemoveBackground", "InvertMask", "JoinImageWithAlpha"} <= kinds
    # the foreground mask (1 = keep) is inverted before it becomes the alpha channel (JoinImageWithAlpha: 1 = transparent)
    inv = next(n for n in tpl.values() if n["class_type"] == "InvertMask")
    assert tpl[inv["inputs"]["mask"][0]]["class_type"] == "RemoveBackground"
    assert tpl[next(n for n in tpl.values() if n["class_type"] == "JoinImageWithAlpha")["inputs"]["alpha"][0]]["class_type"] == "InvertMask"

    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = CutComfy()
    msgs = []
    out = b.remove_background(Image.new("RGB", (40, 30), (10, 10, 10)), lambda f, m, **kw: msgs.append(m))
    assert out.mode == "RGBA" and out.size == (40, 30) and out.getpixel((0, 0))[3] == 0
    g = b.comfy.graphs[0]
    assert next(n for n in g.values() if n["class_type"] == "LoadImage")["inputs"]["image"] in b.comfy.uploads
    assert b.comfy.out_node == "6" and msgs and links_ok(g)

    # the cut-out ends at the subject's outermost pixels (user 1.11.); faint specks do not widen it, an empty result stays
    pic = Image.new("RGBA", (40, 30), (255, 0, 0, 0))
    pic.paste((0, 255, 0, 255), (10, 5, 25, 20))
    pic.putpixel((1, 1), (0, 0, 0, 3))
    cropped = bridge.imaging.crop_to_alpha(pic)
    assert cropped.size == (15, 15) and cropped.getpixel((0, 0)) == (0, 255, 0, 255)
    assert bridge.imaging.crop_to_alpha(Image.new("RGBA", (40, 30), (0, 0, 0, 0))).size == (40, 30)
    b.comfy.output_images = lambda hist, node_id=None: [pic]
    assert b.remove_background(Image.new("RGB", (40, 30))).size == (15, 15)

    # Qwen 3.5 9B describes a picture (describe-image.json): the question defaults to the workflow's own, a typed one replaces it
    d = workflows.load_template(workflows.DESCRIBE_WORKFLOW)
    assert links_ok(d) and bridge.has_tag(d, "image") and bridge.has_tag(d, "prompt") and workflows.writer_name(d) == "Qwen 3.5 9B"

    class TalkComfy(T.FakeComfy):
        def wait(self, pid, on_progress=None, cancelled=None, timeout=0):
            return {"outputs": {"4": {"text": ["A red circle", "on blue."]}}}

    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = TalkComfy()
    assert b.describe_image(Image.new("RGBA", (500, 300), (0, 0, 0, 0))) == "A red circle on blue."
    g = b.comfy.graphs[0]
    ask = next(n for n in g.values() if n["class_type"] == "TextGenerate")["inputs"]["prompt"]
    assert ask.startswith("Describe the main subject") and links_ok(g)
    up = next(iter(b.comfy.uploads.values()))
    assert up.mode == "RGB" and up.size[0] % 32 == 0 and up.size[1] % 32 == 0
    b.describe_image(Image.new("RGB", (64, 64)), question="What colour is the hat?")
    assert next(n for n in b.comfy.graphs[1].values() if n["class_type"] == "TextGenerate")["inputs"]["prompt"] == "What colour is the hat?"

    class MuteComfy(T.FakeComfy):
        def wait(self, pid, on_progress=None, cancelled=None, timeout=0):
            return {"outputs": {"4": {"text": [""]}}}
    b.comfy = MuteComfy()
    try:
        b.describe_image(Image.new("RGB", (64, 64)))
        raise SystemExit("an empty answer is an error")
    except bridge.BridgeError as e:
        assert "no description" in str(e)
    print("ALL OK (remove background, describe)")


if __name__ == "__main__":
    main()
