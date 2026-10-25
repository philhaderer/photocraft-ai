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
    assert workflows.writer_name(workflows.load_template(ROOT / "workflows" / "fibo2-edit.json")) == "Qwen 3.5 9B"
    # Qwen text to image has a workflow of its own (no input picture) with the MOSS text model as prompt enhancer
    q = workflows.load_template(ROOT / "workflows" / "qwen-image-21-t2i.json")
    assert links_ok(q) and not bridge.has_tag(q, "image") and bridge.has_tag(q, "latent") and workflows.writer_name(q) == "Qwen 3.5 9B"
    assert next(n for n in q.values() if n["class_type"] == "CLIPLoader" and "gptq" in n["inputs"]["clip_name"])
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="txt2img", workflow=str(ROOT / "workflows" / "qwen-image-21-t2i.json"), preset="X", run_no=1, base_res=1024, enhance=False)
    req.params = workflows.GenParams(prompt="a red fox", seed=5)
    b.run(req)
    assert not b.comfy.uploads and any(n["class_type"] == "EmptyLatentImage" for n in b.comfy.graphs[0].values())

    # Expand with the Flux 2 / 3 Klein edit workflows (no pc:mask node): no mask is sent, no error
    from PIL import Image
    for wf in ("flux2-klein-edit.json", "flux3-klein-edit.json"):
        pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False, layers=1)
        pc.docs[0].layers[0]["img"].paste((255, 255, 255, 255), (T.W - 40, 0, T.W, T.H))
        b.comfy = T.FakeComfy()
        req = Request(mode="outpaint", workflow=str(ROOT / "workflows" / wf), preset="X", run_no=1, overlap=8)
        req.params = workflows.GenParams(prompt="", seed=5)
        res = b.run(req)
        assert res["layers"] and not any(k.endswith("-mask.png") for k in b.comfy.uploads), wf

    # new layers go on top of the stack; layers that are switched off are not in the picture; a hidden reference is reported
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    top_id = pc.docs[0].layers[-1]["id"]
    pc.docs[0].layers[1]["visible"] = False
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(ROOT / "workflows" / "flux2-klein-edit.json"), preset="X", run_no=1)
    req.params = workflows.GenParams(prompt="make it night", seed=5)
    b.run(req)
    cmds = [c for c, _ in pc.log]
    dup = next(p for c, p in pc.log if c == "image.duplicate")
    assert dup["mergedOnly"] is False and any(c == "layer.delete" for c in cmds)       # the hidden layer was dropped
    first_paste = cmds.index("edit.paste")
    assert any(c == "layer.select" and p.get("layer") == top_id for c, p in pc.log[:first_paste]), "result not placed on top"
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=True)
    pc.docs[0].layers[-1]["visible"] = False
    b.comfy = T.FakeComfy()
    req = Request(mode="reference", workflow=str(ROOT / "workflows" / "qwen-image-21-edit.json"), preset="X", run_no=1, ref_style="simple")
    req.params = workflows.GenParams(prompt="", seed=5)
    try:
        b.run(req)
        raise AssertionError("hidden reference accepted")
    except bridge.BridgeError as e:
        assert "switched off" in str(e)
    # a switched-off TOP layer (the user's case) must not break Refine / Expand: the duplicate has layer ids of its own
    from pccomfy import models
    for wf_name, mode, kw in (("flux3-klein-upscale.json", "refine", {}), ("flux2-klein-upscale.json", "refine", {}),
                              ("flux3-klein-edit.json", "outpaint", {}), ("qwen-image-21-edit.json", "outpaint", {})):
        pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
        pc.docs[0].layers[-1]["visible"] = False        # layers[-1] is the top one in the simulator
        if mode == "outpaint":
            pc.docs[0].layers[0]["img"].paste((255, 255, 255, 255), (T.W - 40, 0, T.W, T.H))   # the empty strip to fill
        b.comfy = T.FakeComfy()
        req = Request(mode=mode, workflow=str(ROOT / "workflows" / wf_name), preset="X", run_no=1, scale=1.0, overlap=8)
        req.params = workflows.GenParams(prompt="", seed=5)
        b.run(req)
        assert b.comfy.graphs, wf_name
    # Refine: the prompt field holds the whole request; empty = the workflow's own prompt, typed text is sent as it is
    for wf_name, default in (("flux3-klein-upscale.json", models.FLUX3_DEFAULT), ("flux2-klein-upscale.json", models.FLUX2_DEFAULT)):
        for typed, want in (("", default), ("A young woman. " + default, "A young woman. " + default)):
            pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
            b.comfy = T.FakeComfy()
            req = Request(mode="refine", workflow=str(ROOT / "workflows" / wf_name), preset="X", run_no=1, scale=1.0)
            req.params = workflows.GenParams(prompt=typed, seed=5)
            b.run(req)
            g = b.comfy.graphs[0]
            node = next(n for n in g.values() if n.get("_meta", {}).get("title", "").startswith("pc:prompt"))
            sent = node["inputs"]["text"]
            assert sent == want, (wf_name, sent)
            assert [n for n in g.values() if n.get("inputs", {}).get("text") == sent or n.get("inputs", {}).get("text") in ([k, 0] for k in g)]
    # the last graph sent to ComfyUI is kept (exchange folder) for diagnosis
    assert (Path(b.exchange) / "last-graph.json").exists()
    # Remove with a selection for Flux 2 / 3 (editor workflows without a mask node): red outline + instruction, no mask upload
    for wf_name in ("flux2-klein-edit.json", "flux3-klein-edit.json"):
        pc, _, b = T.make(tempfile.mkdtemp(), with_sel=True)
        b.comfy = T.FakeComfy()
        req = Request(mode="remove", workflow=str(ROOT / "workflows" / wf_name), preset="X", run_no=1, enhance=False,
                      layer_mask="soft", feather_pct=10.0)
        req.params = workflows.GenParams(prompt="", seed=5)
        res = b.run(req)
        assert res["layers"] and not any(k.endswith("-mask.png") for k in b.comfy.uploads), wf_name
        g = b.comfy.graphs[0]
        txt = next(n for n in g.values() if n.get("_meta", {}).get("title", "").startswith("pc:prompt"))["inputs"]["text"]
        assert "erase" in txt.lower() or "remove" in txt.lower(), txt
    # Fibo text to image: its own workflow without image inputs (empty latent in the size of the canvas), nothing uploaded
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="txt2img", workflow=str(ROOT / "workflows" / "fibo2-t2i.json"), preset="X", run_no=1, enhance=False)
    req.params = workflows.GenParams(prompt="a lighthouse at dusk", seed=5, width=64, height=64)
    res = b.run(req)
    g = b.comfy.graphs[0]
    assert res["layers"] and links_ok(g) and not b.comfy.uploads, b.comfy.uploads
    enc = next(n for n in g.values() if n["class_type"] == "TextEncodeFibo2")
    assert enc["inputs"]["prompt"] == "a lighthouse at dusk" and not any(k.startswith("images.") for k in enc["inputs"])
    lat = next(n for n in g.values() if n["class_type"] == "EmptyLatentImage")["inputs"]
    assert (lat["width"], lat["height"]) == (res["size"][0], res["size"][1])
    # Fibo Refine runs as a whole-image edit
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(ROOT / "workflows" / "fibo2-edit.json"), preset="X", run_no=1, enhance=False)
    req.params = workflows.GenParams(prompt=models.FIBO_REFINE, seed=5)
    assert b.run(req)["layers"]
    assert bridge.layer_visible({"visible": False}) is False and bridge.layer_visible({"hidden": True}) is False
    assert bridge.layer_visible({"id": 1}) is None
    print("ALL OK (round bridge)")


if __name__ == "__main__":
    main()
