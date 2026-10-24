"""Expand can be run again right after an Expand whose result covers the margin.

    python tests/test_expand_rerun.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import bridge, imaging  # noqa: E402


class Pc:
    def __init__(self, name="a.png", size=(300, 100)):
        self.name, self.size, self.hidden = name, size, []

    def document(self):
        return {"width": self.size[0], "height": self.size[1]}

    def session(self):
        return {"documents": [{"name": self.name}]}

    def execute(self, cmd, params=None):
        if cmd == "layer.hideLayers":
            self.hidden.append(params["layer"])


def main():
    b = bridge.Bridge.__new__(bridge.Bridge)
    b.pc = Pc()
    b._last_expand = None
    assert b._rerun_expand(0) is None                       # nothing remembered
    keep = imaging.Box(0, 0, 200, 100)
    b._last_expand = {"doc": "a.png", "size": (300, 100), "keep": keep, "layers": [7, 8]}
    assert b._rerun_expand(0) is keep and b.pc.hidden == [7, 8]   # same document and size: reuse, hide old results
    b.pc.size = (400, 100)
    assert b._rerun_expand(0) is None                       # canvas changed: not the same expand
    b.pc.size, b.pc.name = (300, 100), "b.png"
    assert b._rerun_expand(0) is None                       # another document
    print("ALL OK (expand rerun)")


main()
