"""Insert reference image: the whole bridge run against a small PhotoCraft simulator and a fake ComfyUI.

The top layer is the reference (image_2); all layers below it, flattened in a throw-away duplicate, are the picture
(image_1); the selection says where it goes.

    python tests/test_reference_mode.py
"""
import copy
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge, imaging, workflows  # noqa: E402
from pccomfy.bridge import Bridge, BridgeError, Request  # noqa: E402

W, H = 200, 120
YELLOW = (255, 220, 0, 255)
SEL = (110, 40, 190, 100)  # selection rectangle: where the reference should go (80 x 60)


def rect(color, box):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), color), box[:2])
    return im


class Doc:
    def __init__(self, name, layers, sel=None):
        self.name, self.layers, self.sel, self.active = name, layers, sel, None  # layers: bottom first {id, img, visible}


class FakePC:
    """Just enough of PhotoCraft: documents with layers, duplicate, delete, flatten, fill, save, open, copy/paste."""
    headless = True

    def __init__(self, exchange):
        self.exchange, self.docs, self.active, self.log, self.clip, self._n = Path(exchange), [], 0, [], None, 100

    def connect(self):
        return self

    def _id(self):
        self._n += 1
        return self._n

    @property
    def doc(self):
        return self.docs[self.active]

    @staticmethod
    def composite(doc):
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for l in doc.layers:
            if l["visible"]:
                out.alpha_composite(l["img"])
        return out

    def session(self):
        return {"active": self.active, "documents": [{"index": i, "name": d.name} for i, d in enumerate(self.docs)]}

    def document(self):
        d = self.doc
        return {"width": W, "height": H, "hasSelection": d.sel is not None, "layers": [{"id": l["id"], "visible": l["visible"]} for l in reversed(d.layers)]}

    def execute(self, cmd, params=None):
        params = params or {}
        self.log.append((cmd, params))
        d = self.doc
        if cmd == "image.duplicate":
            nd = copy.deepcopy(d)
            nd.name = params["name"]
            if params.get("mergedOnly"):
                nd.layers = [{"id": self._id(), "img": self.composite(d), "visible": True}]
            self.docs.append(nd)
            self.active = len(self.docs) - 1
        elif cmd == "layer.delete":
            d.layers = [l for l in d.layers if l["id"] != params["layer"]]
        elif cmd == "layer.flattenImage":
            if len(d.layers) < 2:
                from pccomfy.photocraft import PhotoCraftError
                raise PhotoCraftError("layer.flattenImage: nothing to flatten")
            d.layers = [{"id": self._id(), "img": self.composite(d), "visible": True}]
        elif cmd == "layer.new.layer":
            d.layers.append({"id": self._id(), "img": Image.new("RGBA", (W, H), (0, 0, 0, 0)), "visible": True})
            d.active = d.layers[-1]["id"]
        elif cmd == "layer.select":
            d.active = params["layer"]
        elif cmd == "edit.fill":
            lay = next(l for l in d.layers if l["id"] == d.active)
            color = {"white": (255, 255, 255, 255), "black": (0, 0, 0, 255)}[params["contents"]]
            lay["img"].paste(Image.new("RGBA", (W, H), color), (0, 0), d.sel if d.sel is not None else None)
        elif cmd == "select.deselect":
            d.sel = None
        elif cmd == "select.all":
            d.sel = Image.new("L", (W, H), 255)
        elif cmd == "edit.copy":
            self.clip = self.composite(d)
        elif cmd == "edit.paste":
            lay = {"id": self._id(), "img": Image.new("RGBA", (W, H), (0, 0, 0, 0)), "visible": True}
            if params.get("target") != "mask":
                lay["img"] = self.clip.copy()
            d.layers.append(lay)
            return {"layer": lay["id"]}
        elif cmd == "edit.pasteSpecial.pasteInto":
            lay = {"id": self._id(), "img": self.clip.copy(), "visible": True}
            d.layers.append(lay)
            return {"layer": lay["id"]}
        return {}

    def save(self, name):
        self.composite(self.doc).save(self.exchange / name)
        return {}

    def open(self, name):
        im = Image.open(self.exchange / name).convert("RGBA")
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(im.resize((W, H)))
        self.docs.append(Doc(name, [{"id": self._id(), "img": canvas, "visible": True}]))
        self.active = len(self.docs) - 1
        return {}

    def close_active(self):
        del self.docs[self.active]
        self.active = max(0, self.active - 1)

    def activate(self, index):
        self.active = index


class FakeComfy:
    def __init__(self):
        self.uploads, self.graphs = {}, []

    def upload_image(self, image, name):
        self.uploads[name] = image.copy()
        return name

    def queue(self, graph):
        self.graphs.append(graph)
        return "p1"

    def wait(self, pid, on_progress=None, cancelled=None, timeout=0):
        return {"outputs": {"9": {"images": []}}}

    def output_images(self, hist, node_id=None):
        return [Image.new("RGB", (64, 64), (10, 200, 10))]


def make(tmp, with_sel=True, top=None, layers=3):
    pc = FakePC(tmp)
    stack = [{"id": 1, "img": Image.new("RGBA", (W, H), (30, 60, 200, 255)), "visible": True},
             {"id": 2, "img": rect((200, 30, 30, 255), (10, 10, 60, 60)), "visible": True},
             {"id": 3, "img": top if top is not None else rect(YELLOW, (140, 20, 180, 80)), "visible": True}]
    sel = Image.new("L", (W, H), 0)
    sel.paste(255, SEL)
    stacks = {1: [stack[2]], 2: [stack[0], stack[2]], 3: stack}  # layers: how many layers the document has
    pc.docs.append(Doc("scene.png", stacks[layers], sel if with_sel else None))
    return pc, FakeComfy(), Bridge(pc, FakeComfy(), tmp)


def has_yellow(im):
    a = np.asarray(im.convert("RGB")).astype(int)
    return bool(((a[..., 0] > 240) & (a[..., 1] > 190) & (a[..., 1] < 240) & (a[..., 2] < 60)).any())


def run(wf, prompt="", enhance=True, collage=True, style="classic", **kw):
    tmp = tempfile.mkdtemp()
    pc, _, b = make(tmp, **kw)
    b.comfy = FakeComfy()
    req = Request(mode="reference", workflow=str(ROOT / "workflows" / wf) if wf else None, enhance=enhance, ref_collage=collage, ref_style=style)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    res = b.run(req)
    return pc, b, res


def expect_error(text, **kw):
    try:
        run("fibo2-edit-plain.json", **kw)
    except BridgeError as e:
        assert text in str(e), (text, str(e))
        return
    raise AssertionError(f"expected BridgeError containing {text!r}")


def main():
    # imaging helpers
    layer = rect(YELLOW, (140, 20, 180, 80))
    rgba, rgb = imaging.reference_from_layer(layer)
    assert rgba.size == (40, 60) and rgb.size == (40, 60) and rgb.getpixel((5, 5)) == YELLOW[:3]
    big, _ = imaging.reference_from_layer(Image.new("RGBA", (3000, 1500), (1, 2, 3, 255)), max_side=1024)
    assert big.size == (1024, 512)
    try:
        imaging.reference_from_layer(Image.new("RGBA", (50, 50), (0, 0, 0, 0)))
        raise AssertionError("empty layer accepted")
    except ValueError:
        pass
    placed = imaging.paste_reference(Image.new("RGB", (100, 100), "black"), rgba, imaging.Box(10, 10, 80, 60))
    assert placed.getpixel((50, 40)) == YELLOW[:3] and placed.getpixel((12, 12)) == (0, 0, 0)  # 40x60 fits 40x60, centred
    # the sentence: both image tags, the typed text, the placement
    t = bridge.reference_prompt("standing on the left", True, " WHERE")
    assert "<image_1>" in t and "<image_2>" in t and t.endswith("standing on the left") and "already pasted" in t and "WHERE" not in t
    t = bridge.reference_prompt("standing on the left", False, " WHERE")
    assert "WHERE standing on the left" in t and "pasted" not in t       # no copy: the words say where
    assert t.startswith("Place the subject from <image_1> into <image_2>")  # subject first, picture second
    w = bridge.reference_where(imaging.Box(10, 10, 20, 20), imaging.Box(0, 0, 40, 40))
    assert "<image_2>" in w and "centre" in w and "25%" in w

    for wf in ("fibo2-edit-plain.json", "fibo2-edit-vgl-bionic-qwen35-9b.json"):
        # with the rough placement
        pc, b, res = run(wf, prompt="looking at the camera", enhance=True, collage=True)
        g = b.comfy.graphs[0]
        enc = next(n for n in g.values() if n["class_type"] == "TextEncodeFibo2")
        assert "<image_2>" in enc["inputs"]["prompt"] and "<image_1>" in enc["inputs"]["prompt"], wf
        assert "looking at the camera" in enc["inputs"]["prompt"] and "already pasted" in enc["inputs"]["prompt"], wf
        assert not any(n["class_type"] in ("TextGenerate", "VGLBionicEditPrompt", "PreviewAny") for n in g.values()), wf  # text model bypassed
        ref_node = g[enc["inputs"]["images.image_1"][0]]   # the reference is image_1, the picture image_2
        pic_node = g[enc["inputs"]["images.image_2"][0]]
        assert pic_node["inputs"]["image"].endswith("-image.png"), wf
        ref_up = b.comfy.uploads[ref_node["inputs"]["image"]]
        assert ref_up.size == (40, 60) and ref_up.getpixel((20, 30)) == YELLOW[:3], wf
        img_up = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
        assert has_yellow(img_up), wf  # the rough placement is in image_1
        # the picture is all layers below the reference, the reference layer itself is untouched in the document
        assert len(pc.docs) == 1 and [l["id"] for l in pc.docs[0].layers][:3] == [1, 2, 3], wf
        assert pc.docs[0].layers[2]["img"].getpixel((150, 30)) == YELLOW, wf
        assert res["layers"] and not any(c == "layer.layerMask.revealAll" for c, _ in pc.log), wf  # auto: no layer mask
        # no placement: image_1 is the plain picture without the reference
        pc, b, _ = run(wf, enhance=True, collage=False)
        img_up = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
        assert not has_yellow(img_up), wf
        enc = next(n for n in b.comfy.graphs[0].values() if n["class_type"] == "TextEncodeFibo2")
        assert "pasted" not in enc["inputs"]["prompt"] and "Put the subject at the" in enc["inputs"]["prompt"], wf

    # the simple style: the picture is image1, the reference image2, one plain sentence, never a rough placement
    t = bridge.simple_reference_prompt("standing, facing left", "lower right")
    assert t == "Put the subject from image2 into the lower right of the picture from image1. standing, facing left", t
    assert bridge.simple_reference_prompt("", "centre").endswith("of the picture from image1.")
    for wf in ("fibo2-edit-plain.json", "fibo2-edit-vgl-bionic-qwen35-9b.json"):
        pc, b, res = run(wf, prompt="facing the camera", enhance=True, collage=True, style="simple")
        g = b.comfy.graphs[0]
        enc = next(n for n in g.values() if n["class_type"] == "TextEncodeFibo2")
        assert enc["inputs"]["prompt"].startswith("Put the subject from image2 into the "), enc["inputs"]["prompt"]
        assert enc["inputs"]["prompt"].endswith("facing the camera") and "<image" not in enc["inputs"]["prompt"], wf
        pic_node = g[enc["inputs"]["images.image_1"][0]]    # the picture first, the reference second
        ref_node = g[enc["inputs"]["images.image_2"][0]]
        assert pic_node["inputs"]["image"].endswith("-image.png") and ref_node["inputs"]["image"].endswith("-ref.png"), wf
        img_up = next(v for k, v in b.comfy.uploads.items() if k.endswith("-image.png"))
        assert not has_yellow(img_up), wf                     # collage is ignored in this style
        assert res["layers"]

    # errors, each with a clear message
    # no selection: the placed reference layer is the place (its position and size), and the sentence asks for the cut-out
    pc, b, res = run("fibo2-edit-plain.json", prompt="", style="simple", with_sel=False)
    assert res["layers"]
    assert bridge.simple_reference_prompt("", "centre", True).endswith("Remove the background of image2 first.")
    assert "Remove the background" not in bridge.simple_reference_prompt("", "centre")
    expect_error("own layer above the picture", layers=1)
    expect_error("empty", top=Image.new("RGBA", (W, H), (0, 0, 0, 0)))
    try:
        run(None)
        raise AssertionError("built-in graph accepted")
    except BridgeError as e:
        assert "reference slot" in str(e)
    # two layers (one picture layer and the reference) work too: nothing left to flatten after dropping the top
    pc, b, res = run("fibo2-edit-plain.json", layers=2)
    assert res["layers"] and len(pc.docs) == 1
    print("ALL OK (reference mode)")


if __name__ == "__main__":
    main()
