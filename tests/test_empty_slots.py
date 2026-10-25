"""Text to image / image to image with the Fibo workflows: slots the mode cannot fill are removed, not an error.

    python tests/test_empty_slots.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import workflows  # noqa: E402


def tpl(name):
    return workflows.load_template(ROOT / "workflows" / name)


def titles(g):
    return {n.get("_meta", {}).get("title", "") for n in g.values()}


def main():
    p = workflows.GenParams(prompt="a cat", seed=1)
    for name in ("fibo2-edit.json",):
        # img2img: image, no mask -> mask slot gone, picture stays
        g, _ = workflows.apply_template(tpl(name), p, "pic.png", None)
        assert "pc:mask" not in titles(g) and "pc:image" in titles(g), name
        # txt2img: no image, no mask -> both gone, no dangling links
        t = tpl(name)
        if workflows.prompt_writers(t):
            try:   # the text model needs the picture: with it on, Text to image keeps a clear error
                workflows.apply_template(t, p, None, None)
                raise SystemExit("expected error")
            except ValueError as e:
                assert "pc:image" in str(e)
            t = workflows.bypass_prompt_writer(t, "a cat")
        g, _ = workflows.apply_template(t, p, None, None)
        assert not ({"pc:image", "pc:mask", "pc:ref"} & titles(g)), name
        for n in g.values():
            for v in n.get("inputs", {}).values():
                assert not (isinstance(v, list) and str(v[0]) not in g), (name, v)
        # normal fill is unchanged
        g, _ = workflows.apply_template(tpl(name), p, "pic.png", "m.png")
        assert {"pc:image", "pc:mask"} <= titles(g)
    # a workflow whose mask is really used keeps the error
    g = {"1": {"class_type": "LoadImage", "inputs": {"image": "x"}, "_meta": {"title": "pc:mask"}},
         "2": {"class_type": "Foo", "inputs": {"mask": ["1", 0]}, "_meta": {"title": "pc:size"}}}
    try:
        workflows.apply_template(g, p, None, None)
    except ValueError as e:
        assert "pc:mask" in str(e)
    else:
        raise AssertionError("expected error")
    print("ALL OK (empty slots)")


if __name__ == "__main__":
    main()
