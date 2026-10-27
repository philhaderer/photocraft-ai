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
        self.last_sel, self.channels, self.raw = None, {}, None   # select.reselect, saved selections, an opened file's own pixels


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
        return FakePC._composite(doc.layers)

    @staticmethod
    def _composite(layers):
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for l in layers:
            if l["visible"]:
                im = FakePC._composite(l["members"]) if "members" in l else l["img"]
                if l.get("mask") is not None:   # a layer mask (revealSelection): scales the layer's alpha
                    im = im.copy()
                    im.putalpha(Image.fromarray((np.asarray(im.getchannel("A"), dtype=np.uint16)
                                                 * np.asarray(l["mask"], dtype=np.uint16) // 255).astype(np.uint8)))
                out.alpha_composite(im)
        return out

    def session(self):
        return {"active": self.active, "documents": [{"index": i, "name": d.name} for i, d in enumerate(self.docs)]}

    def document(self):
        d = self.doc
        return {"width": W, "height": H, "hasSelection": d.sel is not None, "activeLayer": d.active,
                "layers": [{"id": l["id"], "visible": l["visible"], "name": l.get("name", "Layer"), "hasMask": l.get("mask") is not None,
                            **({"kind": "Group", "children": [{"id": m["id"], "name": m.get("name"), "visible": m["visible"]}
                                                             for m in reversed(l["members"])]} if "members" in l else {})}
                           for l in reversed(d.layers)]}

    def _layer(self, d, lid):
        lay = next((l for l in d.layers + [m for g in d.layers for m in g.get("members", [])] if l["id"] == lid), None)
        if lay is None:
            from pccomfy.photocraft import PhotoCraftError
            raise PhotoCraftError(f"no such layer {lid}")
        return lay

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
            self._layer(d, params["layer"])
            if params.get("mode") == "add":
                d.selected = getattr(d, "selected", [d.active]) + [params["layer"]]
            else:
                d.selected = [params["layer"]]
            d.active = params["layer"]
        elif cmd == "layer.new.groupFromLayers":
            # like PhotoCraft: the selected layers move into a new group in their stack order, at the top one's place
            sel = set(getattr(d, "selected", [d.active]))
            members = [l for l in d.layers if l["id"] in sel]
            assert len(members) == len(sel), "a layer to group is not at the top level"
            at = max(k for k, l in enumerate(d.layers) if l["id"] in sel) - len(members) + 1
            d.layers = [l for l in d.layers if l["id"] not in sel]
            g = {"id": self._id(), "name": params.get("name", "Group"), "visible": True, "members": members}
            d.layers.insert(at, g)
            d.active, d.selected = g["id"], [g["id"]]
            return {"layer": g["id"]}
        elif cmd == "edit.fill":
            lay = next(l for l in d.layers if l["id"] == d.active)
            color = {"white": (255, 255, 255, 255), "black": (0, 0, 0, 255)}[params["contents"]]
            lay["img"].paste(Image.new("RGBA", (W, H), color), (0, 0), d.sel if d.sel is not None else None)
        elif cmd == "select.deselect":
            d.last_sel, d.sel = d.sel if d.sel is not None else d.last_sel, None
        elif cmd == "select.reselect":
            d.sel = d.last_sel
        elif cmd == "select.saveSelection":
            d.channels[params["name"]] = d.sel.copy()
            return {"channel": len(d.channels) - 1, "name": params["name"]}
        elif cmd == "select.loadSelection":
            if params["channel"] == "transparency":
                d.sel = self._layer(d, params["layer"])["img"].getchannel("A")
            else:
                d.sel = d.channels[params["channel"]].copy()
            return {"selected": True}
        elif cmd == "channel.delete":
            del d.channels[params["channel"]]
        elif cmd == "layer.layerMask.revealSelection":   # like PhotoCraft: the selection becomes the mask and is gone
            if d.sel is None:
                from pccomfy.photocraft import PhotoCraftError
                raise PhotoCraftError("layer.layerMask.revealSelection: no selection")
            self._layer(d, params["layer"])["mask"] = d.sel.copy()
            d.last_sel, d.sel = d.sel, None
        elif cmd == "layer.copyToDocument":
            # like PhotoCraft (checked in 0.15.1 and 0.16): a new layer above the destination's active one, placed by the
            # offset from where it lay in the source; the DESTINATION becomes the active document; the clipboard stays
            src = self.docs[params.get("source", self.active)]
            dst = self.docs[params["document"]]
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            img.paste(src.raw, tuple(params.get("offset", (0, 0))))
            lay = {"id": self._id(), "img": img, "visible": True, "name": "Layer"}
            stack = dst.layers
            act = next((l for l in stack if l["id"] == dst.active), None)
            home = next((g for g in stack if any(m["id"] == dst.active for m in g.get("members", []))), None)
            if act is not None and "members" in act:   # like PhotoCraft: a group active = the copy goes INTO it, on top
                act["members"].append(lay)
            elif home is not None:                     # a layer inside a group active: the copy goes above it, in the group
                home["members"].insert(next(k for k, m in enumerate(home["members"]) if m["id"] == dst.active) + 1, lay)
            else:
                at = next((k for k, l in enumerate(stack) if l["id"] == dst.active), len(stack) - 1)
                stack.insert(at + 1, lay)
            dst.active = lay["id"]
            self.active = params["document"]
            return {"document": params["document"], "layers": [lay["id"]], "offset": params.get("offset", [0, 0])}
        elif cmd == "layer.moveTo":     # only what the bridge uses: a layer out of a group, above a top-level layer
            lay = self._layer(d, params["layer"])
            for g in d.layers:
                if lay in g.get("members", []):
                    g["members"].remove(lay)
            d.layers = [l for l in d.layers if l is not lay]
            at = next(k for k, l in enumerate(d.layers) if l["id"] == params["target"])
            d.layers.insert(at + 1 if params.get("position", "above") == "above" else at, lay)
        elif cmd == "layer.renameLayer":
            self._layer(d, params["layer"])["name"] = params["name"]
        elif cmd == "layer.hideLayers":
            lay = self._layer(d, params["layer"])
            lay["visible"] = not lay["visible"]
        elif cmd == "select.all":
            d.sel = Image.new("L", (W, H), 255)
        elif cmd in ("edit.copy", "edit.paste", "edit.pasteSpecial.pasteInto"):
            raise AssertionError(f"{cmd}: a run must not use PhotoCraft's clipboard (it holds what the user copied)")
        return {}

    def save(self, name):
        self.composite(self.doc).save(self.exchange / name)
        return {}

    def open(self, name):
        im = Image.open(self.exchange / name).convert("RGBA")
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(im.resize((W, H)))
        self.docs.append(Doc(name, [{"id": self._id(), "img": canvas, "visible": True}]))
        self.docs[-1].raw = im
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
