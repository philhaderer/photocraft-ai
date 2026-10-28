"""Mix source/new image also for Fibo Refine, which runs as an edit: the result is mixed with the original (stubbed
PhotoCraft and ComfyUI; user 28.10.).

    python tests/test_refine_mix.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as t  # noqa: E402

from pccomfy import bridge, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402


def blends(mode, detail):
    tmp = tempfile.mkdtemp()
    _, _, b = t.make(tmp, layers=2)
    b.comfy = t.FakeComfy()
    req = Request(mode=mode, workflow=str(t.ROOT / "workflows" / "fibo2-edit.json"), enhance=False, detail=detail)
    req.params = workflows.GenParams(prompt="a sharp photo", seed=7)
    calls = []
    real = bridge.Image.blend
    bridge.Image.blend = lambda a, c, alpha: (calls.append(alpha), real(a, c, alpha))[1]
    try:
        b.run(req)
    finally:
        bridge.Image.blend = real
    return calls


def main():
    assert blends("edit", 0.4) == [0.4]          # Fibo Refine (run as edit): mixed with the original
    assert blends("edit", 1.0) == []             # all new: nothing to mix
    print("ALL OK (refine mix)")


if __name__ == "__main__":
    main()
