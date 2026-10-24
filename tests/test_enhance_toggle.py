"""Prompt enhancement off: the typed prompt reaches the image model, the text model drops out of the graph.

    python tests/test_enhance_toggle.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import workflows  # noqa: E402

WF = ROOT / "workflows"
TEXT_MODELS = ("TextGenerate", "VGLBionicEditPrompt", "PreviewAny")


def links_resolve(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values()
               if isinstance(v, list) and v)


def main():
    p = workflows.GenParams(prompt="make the jacket red")
    for name in ("fibo2-edit-vgl-bionic-qwen35-9b.json", "fibo2-edit-vgl-bionic-gemma4-12b.json",
                 "fibo2-edit-vgl-qwen35-convrot.json"):
        tpl = workflows.load_template(WF / name)
        g, out = workflows.apply_template(tpl, p, "img.png", "mask.png")
        assert workflows.prompt_writers(g), name
        off = workflows.bypass_prompt_writer(g, p.prompt)
        assert not workflows.prompt_writers(off), name
        assert not any(n["class_type"] in TEXT_MODELS for n in off.values()), (name, off)
        enc = next(n for n in off.values() if n["class_type"] == "TextEncodeFibo2")
        assert enc["inputs"]["prompt"] == "make the jacket red", enc
        assert links_resolve(off), name
        assert out in off and workflows.bypass_prompt_writer(off, p.prompt) == off  # output kept, idempotent
        assert any(n["class_type"] == "TextGenerate" or n["class_type"] == "VGLBionicEditPrompt" for n in g.values())  # input untouched
    # a workflow without a text model is left alone
    tpl = workflows.load_template(WF / "fibo2-edit-plain.json")
    g, _ = workflows.apply_template(tpl, p, "img.png", "mask.png")
    assert workflows.bypass_prompt_writer(g, p.prompt) == g
    print("ALL OK (enhance toggle)")


if __name__ == "__main__":
    main()
