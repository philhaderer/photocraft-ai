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

# stages and tiles (user 30.10.): a step other than sampling that lasts 2 s gets its word; a sampler entered again is a new tile
import time as _time
from pccomfy import bridge as _bridge
assert _bridge.stage_label({"1": {"class_type": "UNETLoader"}}, "1") == "Loading models"
assert _bridge.stage_label({"1": {"class_type": "SeedVR2Conditioning"}}, "1") == "Restoring detail"
assert _bridge.stage_label({"1": {"class_type": "KSampler"}}, "1") == "" and _bridge.stage_label({}, "9") == ""
assert _bridge._root_id("163.0.1") == "163" and _bridge._root_id("163:2") == "163" and _bridge._root_id(7) == "7"

up = json.loads((ROOT / "workflows" / "flux3-klein-upscale.json").read_text(encoding="utf-8"))
assert _bridge.workflows.main_sampler(up) == "163"


class TileComfy:
    def wait(self, pid, on_progress, cancelled):
        for node, f in (("8", -1), ("163", 0.5), ("164", -1), ("163", 0.25), ("163", 1.0), ("165", -1), ("163", 0.5)):
            on_progress(f, f"step {f}" if f >= 0 else "", node)
        return {}


b2 = Bridge.__new__(Bridge)
b2.comfy, b2.exchange, b2._cancel = TileComfy(), Path(tempfile.mkdtemp()), __import__("threading").Event()
msgs = []
b2._wait("x", up, "wf/up.json", 0, 1, "", lambda f, m, **kw: msgs.append((kw["phase"], m)))
tiles = [m for p, m in msgs if p == "image" and m.startswith("tile")]
assert tiles and tiles[0].startswith("tile 2 ") and tiles[-1].startswith("tile 3 "), msgs        # the first tile has no number
assert not any(p == "stage" for p, _ in msgs)                                                    # nothing lasted 2 s

clock = iter([0.0, 0.5, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0])
_real_mono = _bridge.time.monotonic
_bridge.time.monotonic = lambda: next(clock, 9.0)
try:
    class LoadComfy:
        def wait(self, pid, on_progress, cancelled):
            on_progress(-1, "", "8")
            on_progress(-1, "", "8")                  # the loader runs on: 3 s later it is named
            on_progress(0.5, "step 1/2", "163")
            return {}
    b3 = Bridge.__new__(Bridge)
    b3.comfy, b3.exchange, b3._cancel = LoadComfy(), Path(tempfile.mkdtemp()), __import__("threading").Event()
    seen3 = []
    b3._wait("x", up, "wf/up.json", 0, 1, "", lambda f, m, **kw: seen3.append((kw["phase"], m)))
finally:
    _bridge.time.monotonic = _real_mono
assert ("stage", "Loading models") in seen3 and seen3[-1][0] == "image", seen3
print("ALL OK (stages, tiles)")
