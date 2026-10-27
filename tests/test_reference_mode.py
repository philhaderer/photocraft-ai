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
        return {"width": W, "height": H, "hasSelection": d.sel is not None, "layers": [{"id": l["id"], "visible": l["visible"], "name": l.get("name", "Layer")} for l in reversed(d.layers)]}

    def execute(self, cmd, params=None):
        params = params or {}
        self.log.append((cmd, params))
        d = self.doc
        if cmd == "image.duplicate":
            nd = copy.deepcopy(d)
            nd.name = params["name"]
            for l in nd.layers:     # like PhotoCraft: a duplicate has layers of its own, with new ids
                l["id"] = self._id()
            if params.get("mergedOnly"):
                nd.layers = [{"id": self._id(), "img": self.composite(d), "visible": True}]
            self.docs.append(nd)
            self.active = len(self.docs) - 1
        elif cmd == "layer.delete":
            if not any(l["id"] == params["layer"] for l in d.layers):   # PhotoCraft refuses an id the document does not have
                from pccomfy.photocraft import PhotoCraftError
                raise PhotoCraftError(f'layer.delete: engine.execute: no such layer {params["layer"]}')
            d.layers = [l for l in d.layers if l["id"] != params["layer"]]
        elif cmd == "layer.flattenImage":
            if len(d.layers) < 2:
                from pccomfy.photocraft import PhotoCraftError
                raise PhotoCraftError("layer.flattenImage: nothing to flatten")
            d.layers = [{"id": self._id(), "img": self.composite(d), "visible": True}]
        elif cmd == "layer.new.layer":
            d.layers.append({"id": self._id(), "img": Image.new("RGBA", (W, H), (0, 0, 0, 0)), "visible": True,
                             "name": params.get("name", "Layer")})
            d.active = d.layers[-1]["id"]
            return {"layer": d.active}
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


def run(wf, prompt="", enhance=True, mode="edit", **kw):
    tmp = tempfile.mkdtemp()
    pc, _, b = make(tmp, **kw)
    b.comfy = FakeComfy()
    req = Request(mode=mode, workflow=str(ROOT / "workflows" / wf) if wf else None, enhance=enhance)
    req.params = workflows.GenParams(prompt=prompt or "make it night", seed=7)
    res = b.run(req)
    return pc, b, res


def expect_error(text, **kw):
    try:
        run("fibo2-edit.json", **kw)
    except BridgeError as e:
        assert text in str(e), (text, str(e))
        return
    raise AssertionError(f"expected BridgeError containing {text!r}")


def main():
    # the old "Insert reference image" mode is gone: no mode, no request fields, no helpers
    assert "reference" not in bridge.MODES
    assert not hasattr(bridge, "reference_prompt") and not hasattr(imaging, "reference_from_layer")
    for f in ("ref_style", "ref_collage", "ref_cutout"):
        assert f not in Request.__dataclass_fields__, f
    try:
        run("fibo2-edit.json", mode="reference")
        raise AssertionError("old mode accepted")
    except BridgeError as e:
        assert "Unknown mode" in str(e)
    pc, b, res = run("fibo2-edit.json")          # a plain Edit still works and the layers stay untouched
    assert res["layers"]
    print("ALL OK (reference mode removed)")


if __name__ == "__main__":
    main()
