"""The "Std nodes" tick next to "Prompt" (test A2): only in Flux 3 Upscale of the standard window, off at start, it makes the run
use flux3-klein-upscale-std.json; Easy Mode never shows it. Skipped when Tk cannot open a window.

    python tests/test_std_switch.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-std-")
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui, models  # noqa: E402


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()}) + [gui.STD_WORKFLOW]
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    app.v_model.set("flux3")
    app.v_mode.set("upscale")
    app._on_model()
    app.root.update()
    assert not app.v_std.get() and app._std_shown, "visible in Flux 3 Upscale, off at start"
    assert "upscale-std" not in (app._request().workflow or "")
    app.v_std.set(True)
    assert app._request().workflow.endswith(gui.STD_WORKFLOW)

    app.v_mode.set("edit")
    app._on_model()
    app.root.update()
    assert not app._std_shown and not app.v_std.get(), "gone (and off) in another mode"
    app.v_mode.set("upscale")
    app._on_model()
    app.v_model.set("flux2")
    app._on_model()
    app.root.update()
    assert not app._std_shown, "Flux 3 only"

    app.v_model.set("flux3")
    app.v_mode.set("upscale")
    app._on_model()
    app.v_easy.set(True)
    app.toggle_easy()
    app.root.update()
    assert not app._std_shown, "never in Easy Mode"
    app.v_easy.set(False)
    app.toggle_easy()
    app.root.update()
    app.root.destroy()
    print("ok")


if __name__ == "__main__":
    main()
