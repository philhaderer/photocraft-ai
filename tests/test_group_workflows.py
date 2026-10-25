"""Offline test of the multi-workflow (group) path: fake ComfyUI (tests/fake_comfy.py) + a fake PhotoCraft.

    python tests/test_group_workflows.py
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Bridge, Request  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402


class FakePhotoCraft:
    def __init__(self, exchange: Path):
        self.exchange, self.log, self.next_layer = exchange, [], 100
        self.docs = [{"index": 0, "name": "photo.psd", "width": 800, "height": 600}]
        self.active = 0

    def connect(self):
        return self

    def session(self):
        return {"active": self.active, "documents": self.docs}

    def document(self):
        d = self.docs[self.active]
        return {"width": d["width"], "height": d["height"], "hasSelection": True,
                "layers": [{"id": 1}, {"id": 2}]}

    def execute(self, command, params=None):
        self.log.append((command, params))
        if command == "image.duplicate":
            self.docs.append({"index": len(self.docs), "name": params["name"], "width": 800, "height": 600})
            self.active = len(self.docs) - 1
        if command.startswith("edit.paste") or command == "layer.new.layer":
            self.next_layer += 1
            return {"layer": self.next_layer}
        return {}

    def save(self, name):
        full = self.exchange / name
        if name.endswith("-mask.png"):
            im = Image.new("L", (800, 600), 0)
            im.paste(255, (300, 200, 500, 350))
        else:
            im = Image.new("RGB", (800, 600), (200, 120, 40))
        im.save(full)

    def open(self, name):
        assert (self.exchange / name).exists(), name
        self.docs.append({"index": len(self.docs), "name": name, "width": 1, "height": 1})
        self.active = len(self.docs) - 1

    def close_active(self):
        self.docs.pop()
        self.active = 0

    def activate(self, i):
        self.active = i


def main():
    import shutil
    gdir = Path(tempfile.mkdtemp())   # a group of two workflows, made here (the shipped example was removed)
    for n in ("fibo2-edit.json", "fibo2-edit.json"):
        shutil.copy(ROOT / "workflows" / n, gdir / n)
    group = gdir / "both.group.json"
    group.write_text(json.dumps({"title": "plain, then VGL", "workflows": ["fibo2-edit.json", "fibo2-edit.json"]}))
    srv = subprocess.Popen([sys.executable, str(ROOT / "tests" / "fake_comfy.py"), "8189"])
    time.sleep(1.0)
    try:
        for label, wf, variants, expect in (
            ("group", group, 1, 2),
            ("group x2 variants", group, 2, 4),
            ("single plain", ROOT / "workflows" / "fibo2-edit.json", 1, 1),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                pc = FakePhotoCraft(Path(tmp))
                b = Bridge(pc, ComfyUI("http://127.0.0.1:8189"), tmp)
                req = Request(mode="inpaint", workflow=str(wf), variants=variants,
                              params=workflows.GenParams(prompt="make the shirt red", seed=42))
                res = b.run(req, lambda f, m, **k: None)
                names = [p["name"] for c, p in pc.log if c == "layer.renameLayer"]
                hidden = sum(1 for c, _ in pc.log if c == "layer.hideLayers")
                print(f"{label}: layers={len(res['layers'])} (expected {expect}), hidden={hidden}, size={res['size']}")
                for n in names:
                    print("   ", n)
                assert len(res["layers"]) == expect and hidden == expect - 1
        g = json.loads(Path("/tmp/fake_comfy_last_graph.json").read_text())
        print("last graph (plain): sampler =", {k: v for k, v in g["7"]["inputs"].items() if k in ("seed", "denoise", "steps")},
              "| encode =", {k: v for k, v in g["6"]["inputs"].items() if k in ("prompt", "width", "height", "batch_size")})
        # VGL graph check (apply_template only)
        vgl = workflows.load_template(ROOT / "workflows" / "fibo2-edit.json")
        gv, out = workflows.apply_template(vgl, workflows.GenParams(prompt="add a hat", seed=7, width=1024, height=768, batch=2),
                                           "img.png", "mask.png")
        print("vgl: TextGenerate.prompt =", repr(gv["12"]["inputs"].get("prompt")), "| encode size =",
              (gv["6"]["inputs"]["width"], gv["6"]["inputs"]["height"], gv["6"]["inputs"]["batch_size"]),
              "| encode.prompt link =", gv["6"]["inputs"]["prompt"], "| output node =", out)
        print("ALL OK")
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
