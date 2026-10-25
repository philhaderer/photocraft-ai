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
    req = Request(mode="inpaint", workflow=str(ROOT / "workflows" / "fibo2-edit.json"), variants=variants, preset=preset, run_no=run_no)
    req.params = workflows.GenParams(prompt="a red hat", seed=7)
    b.run(req)
    return [p["name"] for c, p in pc.log if c == "layer.renameLayer"]


def main():
    assert names("Qwen 2.1 Edit", 12) == ["Qwen 2.1 Edit #12"], names("Qwen 2.1 Edit", 12)
    got = names("Fibo plain", 3, variants=2)
    assert sorted(got) == ["Fibo plain #3.1", "Fibo plain #3.2"], got
    tmp = tempfile.mkdtemp()
    pc, _, b = T.make(tmp)
    b.comfy = T.FakeComfy()
    rq = Request(mode="inpaint", workflow=str(ROOT / "workflows" / "fibo2-edit.json"), preset="P", run_no=4, label="res 1024")
    rq.params = workflows.GenParams(prompt="x", seed=1)
    b.run(rq)
    assert [p["name"] for c, p in pc.log if c == "layer.renameLayer"] == ["P #4 [res 1024]"]
    old = names("", 0)
    assert len(old) == 1 and old[0].startswith("AI inpaint"), old        # no preset: the earlier name
    from pccomfy import bridge
    assert bridge.strip_placeholder("<DESCRIBE THE IMAGE>") == ""
    assert bridge.strip_placeholder("a woman <DESCRIBE THE IMAGE>") == "a woman"
    assert bridge.strip_placeholder("a woman with a hat") == "a woman with a hat"
    from PIL import Image, ImageDraw
    from pccomfy import imaging
    im = Image.new("RGB", (200, 200), (100, 100, 100))
    ImageDraw.Draw(im).rectangle((80, 80, 120, 120), fill=(140, 140, 140))
    assert imaging.sharpen(im, 0) is im
    sh = imaging.sharpen(im, 0.5)
    assert sh.size == im.size and sh.getpixel((82, 100))[0] >= im.getpixel((82, 100))[0]
    print("ALL OK (layer names)")


if __name__ == "__main__":
    main()
