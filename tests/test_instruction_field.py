"""pc:prompt must fill `instruction` on VGLBionicEditPrompt nodes (and keep using `text` / `prompt` elsewhere).

    python tests/test_instruction_field.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import workflows  # noqa: E402


def graph(inputs):
    return {"1": {"class_type": "X", "_meta": {"title": "pc:prompt"}, "inputs": inputs}}


def main():
    p = workflows.GenParams(prompt="make it snow")
    for inputs, key in (({"instruction": "", "model": "m"}, "instruction"),
                        ({"text": ""}, "text"),
                        ({"prompt": ""}, "prompt"),
                        ({"text": "", "instruction": ""}, "text")):
        g, _ = workflows.apply_template(graph(dict(inputs)), p, None, None)
        assert g["1"]["inputs"][key] == "make it snow", (inputs, g)
        for other in inputs:
            if other != key and other in ("text", "instruction", "prompt"):
                assert g["1"]["inputs"][other] == "", (inputs, g)
    print("ALL OK")


if __name__ == "__main__":
    main()
