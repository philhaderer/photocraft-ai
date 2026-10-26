"""Phase 0 (gui.py split, models fields, Expand off for Flux 3 / Krea 2, footer without document count).
Run: python tests/test_phase0.py"""
import queue
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets  # noqa: F401  (installs the tkinter stubs)
from pccomfy import gui, models
from pccomfy import gui_lora, gui_modes, gui_prompt, gui_run, gui_state, gui_theme

# 1. App is assembled from the six mixins and no method is defined twice
mixins = (gui_theme.ThemeMixin, gui_prompt.PromptMixin, gui_lora.LoraMixin, gui_modes.ModeMixin, gui_state.StateMixin, gui_run.RunMixin)
assert gui.App.__mro__[1:7] == mixins, gui.App.__mro__
names = [n for m in mixins + (gui.App,) for n in vars(m) if callable(vars(m)[n]) and not n.startswith("__")]
dup = sorted({n for n in names if names.count(n) > 1})
assert not dup, f"defined twice: {dup}"
assert len(names) == 107, len(names)      # 107 methods of the old App, without __init__

# 2. what the other tests and callers read from gui.py is still there
for name in ("BUILTIN", "MODE_LABELS", "SHORT_MODES", "LAYER_MASKS", "REF_STYLES", "CLIP_DEFAULT", "ACCENT", "PROMPT_LINES", "FILL_CONTEXT",
             "word_left", "word_right", "sweep_requests", "duration_text", "scale_text", "parse_list", "winlink", "Tooltip", "run_gui", "DONE_GREEN"):
    assert hasattr(gui, name), name

# 3. models: Expand is off for Flux 3 and Krea 2, everything else is unchanged; the new fields start neutral
by = models.BY_KEY
assert list(by["flux3"].modes) == ["txt2img", "edit", "remove", "upscale"]
assert list(by["krea2"].modes) == ["txt2img"]
assert list(by["flux2"].modes) == ["txt2img", "edit", "remove", "outpaint", "upscale", "refine"]
assert list(by["qwen"].modes) == ["txt2img", "edit", "inpaint", "outpaint", "reference", "remove"]
assert list(by["moss"].modes) == ["txt2img", "outpaint"]
assert [m.key for m in models.MODELS] == ["flux3", "flux2", "qwen", "fibo", "krea2", "moss"]
for m in models.MODELS:
    assert m.max_refs == 0 and m.tag_style == "", m.key
    assert set(m.mode_tips) <= set(m.modes), (m.key, set(m.mode_tips) - set(m.modes))      # no tooltip for a mode the model does not have
assert "Expand" not in by["flux3"].tip and "Expand" not in by["krea2"].tip
assert models.model_for_workflow("krea2-turbo-inpaint.json") is None      # the file stays in workflows/, but no tab uses it


# 4. footer: "PhotoCraft ●   ComfyUI ●", no document count
class FakePC:
    def close(self): pass
    def ping(self): return {"documents": 3}


class FakeComfy:
    def checkpoints(self): return ["a.safetensors"]
    def samplers(self): return ["euler"]
    def clips(self): return []
    def loras(self): return []
    def schedulers(self): return ["normal"]
    def fooocus_inpaint(self): return []


app = object.__new__(gui.App)
app.pc, app.comfy, app.events = FakePC(), FakeComfy(), queue.Queue()
app.refresh()
kind, info = app.events.get(timeout=5)
assert kind == "refresh" and info["pc"] == "PhotoCraft ●" and info["comfy"] == "ComfyUI ●" and "doc" not in info["pc"], info
print("test_phase0 ok")
