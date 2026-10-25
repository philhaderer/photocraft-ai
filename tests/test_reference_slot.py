"""The reference slot (pc:ref -> TextEncodeFibo2 images.image_2) of the Fibo workflows.

    python tests/test_reference_slot.py
"""
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import workflows  # noqa: E402

FILES = sorted(glob.glob(str(ROOT / "workflows" / "fibo2-edit-vgl*.json")) + [str(ROOT / "workflows" / "fibo2-edit-plain.json")])


def links_resolve(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values()
               if isinstance(v, list) and v)


def main():
    p = workflows.GenParams(prompt="put the viking in")
    assert len(FILES) == 4
    for f in FILES:
        name = Path(f).name
        tpl = workflows.load_template(f)
        assert workflows.has_ref_slot(tpl), name
        enc = next(k for k, n in tpl.items() if n["class_type"] == "TextEncodeFibo2")
        # no reference: node and link are gone, the graph is the one-image graph
        g, out = workflows.apply_template(tpl, p, "img.png", "mask.png")
        assert not workflows.has_ref_slot(g) and "images.image_2" not in g[enc]["inputs"], name
        assert "images.image_1" in g[enc]["inputs"] and links_resolve(g) and out in g, name
        assert g[g[enc]["inputs"]["images.image_1"][0]]["inputs"]["image"] == "img.png", name  # the picture is image_1
        # with a reference: the reference comes first (Fibo composes best subject-first), the picture second
        g2, _ = workflows.apply_template(tpl, p, "img.png", "mask.png", ref_name="ref.png")
        ref = g2[g2[enc]["inputs"]["images.image_1"][0]]
        pic = g2[g2[enc]["inputs"]["images.image_2"][0]]
        assert ref["class_type"] == "LoadImage" and ref["inputs"]["image"] == "ref.png", name
        assert pic["class_type"] == "LoadImage" and pic["inputs"]["image"] == "img.png" and links_resolve(g2), name
        # the template itself is never changed
        assert workflows.has_ref_slot(tpl) and tpl[enc]["inputs"]["images.image_2"][0] in tpl, name
        # the prompt-enhancement bypass still works with a reference
        off = workflows.bypass_prompt_writer(g2, p.prompt)
        assert links_resolve(off) and "images.image_2" in off[enc]["inputs"], name
    # a workflow without a slot cannot take a reference
    tpl = workflows.load_template(FILES[0])
    del tpl[[k for k, n in tpl.items() if "pc:ref" in n.get("_meta", {}).get("title", "")][0]]
    for n in tpl.values():
        n["inputs"].pop("images.image_2", None)
    try:
        workflows.apply_template(tpl, p, "img.png", "mask.png", ref_name="ref.png")
        raise SystemExit("expected ValueError")
    except ValueError as e:
        assert "reference slot" in str(e)
    print("ALL OK (reference slot)")


if __name__ == "__main__":
    main()
