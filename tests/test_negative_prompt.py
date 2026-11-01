"""The negative prompt box works with MOSS Text to image (the only workflow with a real negative prompt): typed text goes into the
node, an empty box keeps the workflow's own text; the box is enabled there and greyed out for a workflow without that node.

    python tests/test_negative_prompt.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import workflows  # noqa: E402
from pccomfy.workflows import GenParams  # noqa: E402


def neg_text(negative: str) -> str:
    tpl = workflows.load_template(ROOT / "workflows" / "moss-image-t2i.json")
    g, _out = workflows.apply_template(tpl, GenParams(prompt="a cat", negative=negative), None, None)
    return g["21"]["inputs"]["text"]


def main():
    tpl = workflows.load_template(ROOT / "workflows" / "moss-image-t2i.json")
    assert "negative" in workflows._tags(tpl["21"])
    assert neg_text("blurry, text") == "blurry, text"
    assert neg_text("") == tpl["21"]["inputs"]["text"] and "worst quality" in neg_text("   ")
    flux = workflows.load_template(ROOT / "workflows" / "flux3-klein-t2i.json")
    assert not any("negative" in workflows._tags(n) for n in flux.values() if isinstance(n, dict))
    print("ALL OK (negative prompt)")


if __name__ == "__main__":
    main()
