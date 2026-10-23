"""_set_bar must not touch Tk when nothing changed (that caused the blinking). Run: python tests/test_bars.py"""
import sys, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets  # noqa: F401  (installs the tkinter stubs)
from pccomfy import gui


class Bar:
    def __init__(self): self.calls = []; self.mode = "determinate"
    def stop(self): self.calls.append("stop")
    def start(self, *_): self.calls.append("start")
    def configure(self, **kw): self.calls.append(("cfg", tuple(sorted(kw)))); self.mode = kw.get("mode", self.mode)
    def __getitem__(self, k): return {"mode": self.mode, "maximum": 1.0}[k]


class V:
    def __init__(self): self.v = ""
    def get(self): return self.v
    def set(self, x): self.v = x


app = object.__new__(gui.App)
app.bars = {"prompt": Bar(), "image": Bar()}
app.v_pl, app.v_il = V(), V()
for _ in range(20):
    app._set_bar("prompt", 1.0, None, None)
assert app.bars["prompt"].calls.count("stop") == 0 and len(app.bars["prompt"].calls) == 1, app.bars["prompt"].calls
for _ in range(20):
    app._set_bar("image", -1, "x", 3)
assert app.bars["image"].calls.count("start") == 1
print("ALL OK (bars)")
