"""BBOX in Multi Image Edit (Flux 3): the selection becomes the box <obj_1>. The graph change (workflows.add_layout) and the whole
bridge run against the PhotoCraft simulator and the fake ComfyUI of test_reference_mode.

    python tests/test_bbox.py
"""
import json
import sys
import tempfile

import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as t  # noqa: E402
from pccomfy import bridge, models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

WF = str(t.ROOT / "workflows" / "flux3-klein-edit.json")


def run(prompt, bbox=True, with_sel=True, layer_mask="auto"):
    tmp = tempfile.mkdtemp()
    pc, _, b = t.make(tmp, with_sel=with_sel)
    b.comfy = t.FakeComfy()
    req = Request(mode="edit", workflow=WF, bbox=bbox, enhance=False, layer_mask=layer_mask)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    res = b.run(req)
    return pc, b, res


def prompt_node(graph):
    return next(n for n in graph.values() if "pc:prompt" in n.get("_meta", {}).get("title", ""))


def main():
    assert {m.key for m in models.MODELS if m.bbox} == {"flux3"}      # BBOX is a Flux 3 switch only

    # the graph change on its own
    g = json.loads(Path(WF).read_text(encoding="utf-8"))
    n_before = len(g)
    old_text = prompt_node(g)["inputs"]["text"]
    workflows.add_layout(g, (110, 40, 80, 60), (200, 120), desc="a tent")
    assert len(g) == n_before + 2
    bb = next(v for v in g.values() if v["class_type"] == "CreateBoundingBoxes")
    lay_id, lay = next((k, v) for k, v in g.items() if v["class_type"] == "Flux3LayoutPrompt")
    assert bb["inputs"]["width"] == 200 and bb["inputs"]["height"] == 120 and bb["inputs"]["editor_state"] == {"__value__": []}
    boxes = json.loads(bb["inputs"]["bboxes"])
    assert boxes == [{"x": 110, "y": 40, "width": 80, "height": 60,
                      "metadata": {"type": "obj", "text": "", "desc": "a tent", "palette": []}}]
    assert lay["inputs"]["prompt"] == old_text and lay["inputs"]["element"][1] == 2
    assert prompt_node(g)["inputs"]["text"] == [lay_id, 0]            # the text encoder reads the layout node now
    assert bb is g[lay["inputs"]["element"][0]]

    # a run with a selection: the box is the selection, the sentence is added, the selection is still there afterwards
    pc, b, res = run("replace the tent with a dog")
    graph = b.comfy.graphs[-1]
    bb = next(v for v in graph.values() if v["class_type"] == "CreateBoundingBoxes")
    x, y, w, h = t.SEL[0], t.SEL[1], t.SEL[2] - t.SEL[0], t.SEL[3] - t.SEL[1]
    got = json.loads(bb["inputs"]["bboxes"])[0]
    assert (got["x"], got["y"], got["width"], got["height"]) == (x, y, w, h), got
    assert (bb["inputs"]["width"], bb["inputs"]["height"]) == (t.W, t.H)
    lay = next(v for v in graph.values() if v["class_type"] == "Flux3LayoutPrompt")
    assert lay["inputs"]["prompt"] == "replace the tent with a dog " + bridge.BBOX_SENTENCE, lay["inputs"]["prompt"]
    assert pc.doc.sel is not None, "BBOX must leave the user's selection as it is"
    assert res["layers"]

    # the layer mask: the box grown by 50 % on every side, soft edge; a hard picture-sized layer without it
    from pccomfy import imaging  # noqa: E402
    box = imaging.Box(x, y, w, h)
    m = imaging.box_margin_mask(box, (t.W, t.H), bridge.BBOX_MARGIN, 0.0)
    a = np.asarray(m)
    gx0, gy0 = max(0, x - w // 2), max(0, y - h // 2)
    gx1, gy1 = min(t.W, x + w + w // 2), min(t.H, y + h + h // 2)
    assert a[gy0:gy1, gx0:gx1].min() == 255 and a.sum() == 255 * (gx1 - gx0) * (gy1 - gy0)
    soft = imaging.box_margin_mask(box, (t.W, t.H), bridge.BBOX_MARGIN, 20.0)
    s_ = np.asarray(soft)
    assert s_[(y + h // 2), (x + w // 2)] == 255 and 0 < s_[gy0, (x + w // 2)] < 255
    assert s_[0, 0] == 0
    n_masked = lambda pc_: sum(1 for l in pc_.doc.layers if l.get("mask") is not None)
    pc, b, res = run("replace the tent with a dog")
    assert n_masked(pc) >= 1, "BBOX with auto layer mask must give the result a layer mask"
    assert pc.doc.sel is not None, "the selection must come back after the soft mask used it"
    pc, b, res = run("replace the tent with a dog", layer_mask="none")
    assert n_masked(pc) == 0, "layer mask none = no mask"

    # the user's own <obj_1> is left alone
    pc, b, res = run("replace the tent <obj_1> with a dog")
    lay = next(v for v in b.comfy.graphs[-1].values() if v["class_type"] == "Flux3LayoutPrompt")
    assert lay["inputs"]["prompt"] == "replace the tent <obj_1> with a dog"

    # no selection: a normal run, no box nodes
    pc, b, res = run("make it night", with_sel=False)
    assert all(v["class_type"] not in ("CreateBoundingBoxes", "Flux3LayoutPrompt") for v in b.comfy.graphs[-1].values())
    assert prompt_node(b.comfy.graphs[-1])["inputs"]["text"] == "make it night"

    # BBOX off: the selection is ignored as before (the whole picture is selected, no box nodes)
    pc, b, res = run("make it night", bbox=False)
    assert all(v["class_type"] not in ("CreateBoundingBoxes", "Flux3LayoutPrompt") for v in b.comfy.graphs[-1].values())
    print("ok")


if __name__ == "__main__":
    main()
