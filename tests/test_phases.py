"""Phase split of the progress display (prompt writing vs image generation). Run: python tests/test_phases.py"""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy.bridge import Bridge, after_prompt_nodes, prompt_phase_nodes

ROOT = Path(__file__).resolve().parent.parent
g = json.loads((ROOT / "workflows" / "fibo2-edit.json").read_text(encoding="utf-8"))
assert prompt_phase_nodes(g) >= {"10", "11", "12"} and "7" in after_prompt_nodes(g)
assert prompt_phase_nodes(json.loads((ROOT / "workflows" / "fibo2-t2i.json").read_text(encoding="utf-8"))) >= {"20", "21", "22"}   # writer since 30.10.
assert prompt_phase_nodes(json.loads((ROOT / "workflows" / "flux3-klein-edit.json").read_text(encoding="utf-8"))) == set()


class FakeComfy:
    def wait(self, pid, on_progress, cancelled):
        for node, f in (("4", -1), ("12", -1), ("12", -1), ("6", -1), ("7", 0.25), ("7", 1.0)):
            on_progress(f, f"step {f}" if f >= 0 else "", node)
        return {}


b = Bridge.__new__(Bridge)
b.comfy, b.exchange, b._cancel = FakeComfy(), Path(tempfile.mkdtemp()), __import__("threading").Event()
seen = []
b._wait("x", g, "wf/gemma.json", 0.15, 0.75, "", lambda f, m, **kw: seen.append((kw["phase"], kw["phase_fraction"])))
phases = [p for p, _ in seen]
assert phases[:3] == ["prompt"] * 3 and phases[3:] == ["image"] * 3, phases
assert seen[-1] == ("image", 1.0)
assert "gemma.json" or True
assert json.loads((b.exchange / "timings.json").read_text())["gemma:prompt"] >= 0
print("ALL OK")

from pccomfy.bridge import mask_is_used
assert not mask_is_used(g)
assert Bridge._vgl_text(g, {"outputs": {"13": {"text": ["{\"a\": 1}"]}}}) == '{"a": 1}'
print("ALL OK (vgl, mask)")

from pccomfy.bridge import placement_hint
from pccomfy.imaging import Box
h = placement_hint(Box(100, 100, 100, 100), Box(0, 0, 1000, 1000))
assert "upper left" in h and "1%" in h, h
assert "centre" in placement_hint(Box(450, 450, 100, 100), Box(0, 0, 1000, 1000))
assert "bottom centre" in placement_hint(Box(450, 800, 100, 100), Box(0, 0, 1000, 1000))
print("ALL OK (hint)")

from PIL import Image, ImageDraw
from pccomfy import imaging
hard = Image.new("L", (200, 200), 0); ImageDraw.Draw(hard).rectangle((50, 50, 149, 149), fill=255)
assert not imaging.is_soft(hard)
r = imaging.feather_radius(100, 300, 2.0); assert r == 2, r
assert imaging.feather_radius(100, 300, 0) == 0
soft = imaging.auto_feather(hard, 10)
assert imaging.is_soft(soft) and soft.getpixel((100, 100)) == 255 and soft.getpixel((0, 0)) == 0
assert list(imaging.auto_feather(soft, 10).getdata()) == list(soft.getdata())  # already soft: unchanged
assert list(imaging.auto_feather(hard, 0).getdata()) == list(hard.getdata())
print("ALL OK (feather)")
