"""Cut-out of a reference image: birefnet-remove-bg.json (ComfyUI's own BiRefNet nodes) and Bridge.remove_background.

    python tests/test_removebg.py
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
    print("ALL OK (remove background)")


if __name__ == "__main__":
    main()
