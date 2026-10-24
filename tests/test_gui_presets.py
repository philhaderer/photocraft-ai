"""Preset save/load logic of the bridge window, run against a stubbed Tk (no display, no tkinter needed).

    python tests/test_gui_presets.py
"""
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp()
os.environ["PCCOMFY_HOME"] = TMP


class TclError(Exception):
    pass


class Var:
    def __init__(self, master=None, value=None, **k):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class IntVar(Var):
    def get(self):
        try:
            return int(float(self._v))
        except (TypeError, ValueError):
            raise TclError("expected integer")


class DoubleVar(Var):
    def get(self):
        try:
            return float(self._v)
        except (TypeError, ValueError):
            raise TclError("expected float")


class Widget:
    def __init__(self, *a, **k):
        self._o = dict(k)

    def __setitem__(self, k, v):
        self._o[k] = v

    def __getitem__(self, k):
        return self._o.get(k, ())

    def configure(self, *a, **k):
        self._o.update(k)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None


class Text(Widget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._t = ""

    def insert(self, idx, s):
        self._t += s

    def delete(self, a, b):
        self._t = ""

    def get(self, a, b):
        return self._t + "\n"


tk = types.ModuleType("tkinter")
ttk = types.ModuleType("tkinter.ttk")
mb = types.ModuleType("tkinter.messagebox")
sd = types.ModuleType("tkinter.simpledialog")
tk.Tk = tk.Toplevel = Widget
tk.StringVar, tk.IntVar, tk.DoubleVar, tk.BooleanVar = Var, IntVar, DoubleVar, Var
tk.Text, tk.TclError = Text, TclError
for n in ("Frame", "Label", "Combobox", "Button", "Radiobutton", "Checkbutton", "Spinbox", "LabelFrame",
          "Progressbar", "Style", "Notebook", "Scale"):
    setattr(ttk, n, Widget)
mb.askyesno = lambda *a, **k: True
sd.askstring = lambda *a, **k: None
tk.ttk, tk.messagebox, tk.simpledialog = ttk, mb, sd
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb, "tkinter.simpledialog": sd,
                    "tomllib": types.SimpleNamespace(load=lambda f: {})})

sys.path.insert(0, str(ROOT))
from pccomfy import config as cfgmod, gui  # noqa: E402


def main():
    app = gui.App(cfgmod.load())
    app.cb_workflow["values"] = [gui.BUILTIN, "fibo2-edit-both.group.json", "fibo2-edit-plain.json"]
    app.cb_clip["values"] = [gui.CLIP_DEFAULT, "qwen_a.safetensors", "gemma.safetensors"]

    def setup():
        app.v_mode.set("inpaint")
        app.v_workflow.set("fibo2-edit-both.group.json")
        app.v_clip.set("gemma.safetensors")
        app.t_prompt.delete("1.0", "end")
        app.t_prompt.insert("1.0", "make the jacket red")
        app.t_neg.delete("1.0", "end")
        app.v_denoise.set(0.8)
        app.v_res.set(768)
        app.v_variants.set(3)
        app.v_lmask.set(gui.LAYER_MASKS["selection"])
        app.v_overlap.set(96)

    # save
    setup()
    sd.askstring = lambda *a, **k: "My Test!"
    app.save_preset_as()
    f = Path(TMP) / "presets" / "My Test_.json"
    assert f.exists(), "preset file missing"
    data = json.loads(f.read_text(encoding="utf-8"))
    s = data["settings"]
    assert s["prompt"] == "make the jacket red" and s["clip"] == "gemma.safetensors" and s["base_res"] == 768, s
    assert s["layer_mask"] == "selection" and s["overlap"] == 96 and s["variants"] == 3
    assert app.v_preset.get() == "My Test_" and app.cb_preset["values"] == ["My Test_"]
    print("save OK:", sorted(s))

    # change everything, then load
    app.v_mode.set("img2img")
    app.v_workflow.set(gui.BUILTIN)
    app.v_clip.set(gui.CLIP_DEFAULT)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "something else")
    app.v_denoise.set(0.3)
    app.v_res.set(512)
    app.v_overlap.set(8)
    app.load_preset("My Test_")
    assert app.v_mode.get() == "inpaint" and app.v_workflow.get() == "fibo2-edit-both.group.json"
    assert app.v_clip.get() == "gemma.safetensors" and app.v_res.get() == 768 and app.v_denoise.get() == 0.8
    assert app.t_prompt.get("1.0", "end").strip() == "make the jacket red" and app.v_overlap.get() == 96
    assert app.v_lmask.get() == gui.LAYER_MASKS["selection"]
    print("load OK:", app.v_status.get())

    # preset that refers to things this machine does not have
    s2 = dict(s, workflow="nope.json", clip="missing.safetensors", steps="abc")
    (Path(TMP) / "presets" / "Odd.json").write_text(json.dumps({"format": 1, "settings": s2}), encoding="utf-8")
    app.refresh_presets()
    app.load_preset("Odd")
    assert "workflow nope.json not found" in app.v_status.get() and "text model missing" in app.v_status.get()
    assert app.v_workflow.get() == "fibo2-edit-both.group.json" and app.v_clip.get() == gui.CLIP_DEFAULT
    print("missing items OK:", app.v_status.get())

    # the shipped example preset
    shutil.copy(ROOT / "presets" / "Fibo both.json", Path(TMP) / "presets" / "Fibo both.json")
    app.refresh_presets()
    app.load_preset("Fibo both")
    assert app.v_workflow.get() == "fibo2-edit-both.group.json" and app.v_denoise.get() == 1.0
    print("example preset OK")

    # the normal request path still works and remembers the preset name
    app.v_preset.set("My Test_")
    req = app._request()
    app._save_state(req)
    assert json.loads((Path(TMP) / "state.json").read_text(encoding="utf-8"))["preset"] == "My Test_"
    print("request/state OK:", req.mode, Path(req.workflow).name)

    # errors get the red badge (no dialog), normal messages clear it
    shown = []
    app.lbl_err.pack = lambda *a, **k: shown.append("on")
    app.lbl_err.pack_forget = lambda: shown.append("off")
    app._status("Error: ComfyUI is not reachable", error=True)
    app._status("Saved.")
    app.v_workflow.set("fibo2-edit-both.group.json")
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "x")
    app._status("Loaded.")
    assert shown == ["on", "off", "off"] and app.v_status.get() == "Loaded.", shown
    print("status badge OK")

    # delete
    app.delete_preset()
    assert not f.exists() and app.v_preset.get() == ""
    print("delete OK")
    print("ALL OK")


if __name__ == "__main__":
    main()
