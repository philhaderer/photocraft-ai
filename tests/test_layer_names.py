"""Layers are named after the preset and a running number.

    python tests/test_layer_names.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
import test_reference_mode as T  # noqa: E402


class Two(T.FakeComfy):
    def output_images(self, hist, node_id=None):
        return super().output_images(hist, node_id) * 2


def names(preset, run_no, variants=1):
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp)
    b.comfy = Two() if variants > 1 else T.FakeComfy()
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / "fibo2-edit-plain.json"), variants=variants, preset=preset, run_no=run_no)
    req.params = workflows.GenParams(prompt="a red hat", seed=7)
    b.run(req)
    return [p["name"] for c, p in pc.log if c == "layer.renameLayer"]


def main():
    assert names("Qwen 2.1 Edit", 12) == ["Qwen 2.1 Edit #12"], names("Qwen 2.1 Edit", 12)
    got = names("Fibo plain", 3, variants=2)
    assert sorted(got) == ["Fibo plain #3.1", "Fibo plain #3.2"], got
    old = names("", 0)
    assert len(old) == 1 and old[0].startswith("AI inpaint"), old        # no preset: the earlier name
    print("ALL OK (layer names)")


if __name__ == "__main__":
    main()
