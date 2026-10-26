"""Multi Image Edit, the logic: the slots (refslots.py), the reference slots of the four edit workflows and the run through
the bridge with reference images.

    python tests/test_refslots.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402
from pccomfy import bridge, models, refslots, workflows  # noqa: E402
from pccomfy.bridge import BridgeError, Request  # noqa: E402
from pccomfy.refslots import RefError, RefSlots  # noqa: E402
import test_reference_mode as T  # noqa: E402

WF = {"qwen": "qwen-image-21-edit.json", "fibo": "fibo2-edit.json", "flux2": "flux2-klein-edit.json", "flux3": "flux3-klein-edit.json"}


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def acyclic(g):
    seen, stack = set(), set()

    def visit(nid):
        if nid in stack:
            return False
        if nid in seen:
            return True
        stack.add(nid)
        ok = all(visit(str(v[0])) for v in g[nid].get("inputs", {}).values() if isinstance(v, list) and v)
        stack.discard(nid)
        seen.add(nid)
        return ok
    return all(visit(n) for n in g)


def loads(g, cls="LoadImage"):
    return [n for n in g.values() if n["class_type"] == cls]


def main():
    # ---- the slots ----
    rs = RefSlots()
    try:
        rs.add(Image.new("RGB", (4, 4)))
        raise SystemExit("a model without slots takes no image")
    except RefError:
        pass
    q = models.BY_KEY["qwen"]
    rs.set_model(q.max_refs, q.tag_style)
    rs.add(Image.new("RGB", (4, 4), "red"), "a.png")
    rs.add(Image.new("RGBA", (4, 4), (0, 0, 255, 0)), "b.png")
    try:
        rs.add(Image.new("RGB", (4, 4)))
        raise SystemExit("the third image does not fit")
    except RefError as e:
        assert "full" in str(e)
    assert rs.free == 0 and rs.tag(0) == "<image2>" and rs.tag(1) == "<image3>" and rs.picture_tag() == "<image1>"
    assert rs.hint() == "picture = <image1>, reference 1 = <image2>, reference 2 = <image3>"
    f3 = models.BY_KEY["flux3"]
    rs.set_model(f3.max_refs, f3.tag_style)           # {i} counts from 0: the picture is ref_image_0
    assert rs.picture_tag() == "<ref_image_0>" and rs.tag(0) == "<ref_image_1>" and rs.free == 1
    f2 = models.BY_KEY["flux2"]
    rs.set_model(f2.max_refs, f2.tag_style)
    assert rs.tag(0) == "image 2"
    # a switch to a model with fewer slots keeps the images but sends only the first ones
    rs.add(Image.new("RGB", (4, 4), "green"), "c.png")
    rs.set_model(1, "<image{n}>")
    assert [it.name for it in rs.active] == ["a.png"] and [it.name for it in rs.overflow] == ["b.png", "c.png"] and len(rs.images()) == 1
    rs.set_model(3, "image {n}")
    rs.move(2, 0)
    assert [it.name for it in rs.items] == ["c.png", "a.png", "b.png"]
    rs.remove(1)
    assert [it.name for it in rs.items] == ["c.png", "b.png"]
    # a cut-out keeps the original for "back"
    cut = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    rs.replace(0, cut)
    assert rs.items[0].cut_out and rs.items[0].image is cut
    rs.revert(0)
    assert not rs.items[0].cut_out and rs.items[0].image.getpixel((0, 0)) == (0, 128, 0)
    # files
    tmp = Path(tempfile.mkdtemp())
    Image.new("RGB", (8, 6), "blue").save(tmp / "one two.png")
    (tmp / "note.txt").write_text("x")
    rs.clear()
    n, notes = rs.add_files([tmp / "note.txt", tmp / "one two.png"])
    assert n == 1 and len(notes) == 1 and rs.items[0].name == "one two.png"
    assert [p.name for p in refslots.parse_drop_data("{%s} %s/b.png" % (tmp / "one two.png", tmp))] == ["one two.png", "b.png"]
    # what is sent: flat, at most 1024 px, multiples of the model's grid
    big = Image.new("RGBA", (3000, 1500), (255, 0, 0, 0))
    out = refslots.prepare_image(big, 32)
    assert out.mode == "RGB" and out.size == (1024, 512) and out.getpixel((0, 0)) == (255, 255, 255)
    assert refslots.prepare_image(Image.new("RGB", (100, 75)), 32).size == (96, 64)
    assert refslots.prepare_image(Image.new("RGB", (5, 5)), 16).size == (16, 16)

    # ---- the workflows ----
    p = workflows.GenParams(prompt="put the dog from image 2 on the sofa")
    for key, wf in WF.items():
        tpl = workflows.load_template(ROOT / "workflows" / wf)
        n_max = models.BY_KEY[key].max_refs
        assert workflows.ref_slot_count(tpl) == n_max and links_ok(tpl), key
        base = len(loads(tpl))
        none, _ = workflows.apply_template(tpl, p, "pic.png", None)
        assert links_ok(none) and acyclic(none), key
        assert [n["inputs"]["image"] for n in loads(none)] == ["pic.png"], key
        assert not workflows.has_ref_slot(none), key
        for k in range(1, n_max + 1):
            g, out = workflows.apply_template(tpl, p, "pic.png", None, [f"r{i}.png" for i in range(1, k + 1)], ref_first=False)
            assert links_ok(g) and acyclic(g) and out in g, (key, k)
            names = sorted(n["inputs"]["image"] for n in loads(g))
            assert names == sorted(["pic.png"] + [f"r{i}.png" for i in range(1, k + 1)]), (key, k, names)
            assert sum(1 for n in loads(g) if n["inputs"]["image"].startswith("r")) == k, (key, k)
        try:
            workflows.apply_template(tpl, p, "pic.png", None, [f"r{i}.png" for i in range(n_max + 1)])
            raise SystemExit("too many images must fail: " + key)
        except ValueError as e:
            assert "room for" in str(e), e
    # Flux 2: the chains stay closed when slots are dropped: guider -> last used ReferenceLatent -> ... -> the text
    t = workflows.load_template(ROOT / "workflows" / WF["flux2"])
    for k in (0, 1, 2, 3):
        g, _ = workflows.apply_template(t, p, "pic.png", None, [f"r{i}.png" for i in range(k)])
        assert len(loads(g, "ReferenceLatent")) == 2 * (k + 1) and len(loads(g, "VAEEncode")) == k + 1, k
        guider = loads(g, "CFGGuider")[0]["inputs"]
        for side, src in (("positive", "CLIPTextEncode"), ("negative", "ConditioningZeroOut")):
            nid, hops = str(guider[side][0]), 0
            while g[nid]["class_type"] == "ReferenceLatent":
                nid, hops = str(g[nid]["inputs"]["conditioning"][0]), hops + 1
            assert g[nid]["class_type"] == src and hops == k + 1, (k, side)
    # Flux 3: the pictures are images.image0 (the picture), image1 ...
    t = workflows.load_template(ROOT / "workflows" / WF["flux3"])
    g, _ = workflows.apply_template(t, p, "pic.png", None, ["a.png", "b.png"])
    assert sorted(k for k in loads(g, "ReferenceMultiLatent")[0]["inputs"] if k.startswith("images.")) == ["images.image0", "images.image1", "images.image2"]
    # Fibo / Qwen: picture first, references behind it
    for key in ("fibo", "qwen"):
        t = workflows.load_template(ROOT / "workflows" / WF[key])
        g, _ = workflows.apply_template(t, p, "pic.png", None, ["a.png", "b.png"], ref_first=False)
        enc = next(n for n in g.values() if n["class_type"].startswith("TextEncode") and "images.image_1" in n["inputs"])
        order = [g[str(enc["inputs"][f"images.image_{i}"][0])]["inputs"]["image"] for i in (1, 2, 3)]
        assert order == ["pic.png", "a.png", "b.png"], (key, order)

    # ---- through the bridge ----
    for key, wf in WF.items():
        for k in range(models.BY_KEY[key].max_refs + 1):
            pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
            b.comfy = T.FakeComfy()
            req = Request(mode="edit", workflow=str(ROOT / "workflows" / wf), enhance=False, preset="X", run_no=1,
                          refs=[Image.new("RGBA", (300 + 10 * i, 200), (255, 0, 0, 0)) for i in range(k)])
            req.params = workflows.GenParams(prompt="swap the hat", seed=3)
            b.run(req)
            g = b.comfy.graphs[0]
            sent = [im for name, im in b.comfy.uploads.items() if "-ref" in name]
            assert len(sent) == k and links_ok(g), (key, k)
            mult = 32 if key == "qwen" else 16
            assert all(im.mode == "RGB" and im.size[0] % mult == 0 and im.size[1] % mult == 0 for im in sent), (key, k)
            assert all(im.getpixel((0, 0)) == (255, 255, 255) for im in sent), "transparent areas turn white"
    # errors: too many images, a mode that takes none
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="edit", workflow=str(ROOT / "workflows" / WF["qwen"]), enhance=False, refs=[Image.new("RGB", (64, 64))] * 3)
    req.params = workflows.GenParams(prompt="x", seed=1)
    try:
        b.run(req)
        raise SystemExit("three images do not fit into Qwen")
    except BridgeError as e:
        assert "room for 2" in str(e), e
    req = Request(mode="upscale", workflow=str(ROOT / "workflows" / "flux3-klein-upscale.json"), refs=[Image.new("RGB", (64, 64))])
    req.params = workflows.GenParams(prompt="x", seed=1)
    try:
        b.run(req)
        raise SystemExit("Upscale takes no reference images")
    except BridgeError as e:
        assert "Edit, Fill" in str(e), e
    print("ALL OK (refslots)")


if __name__ == "__main__":
    main()
