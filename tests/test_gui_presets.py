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

    def winfo_width(self):
        return 420

    def winfo_reqheight(self):
        return 700

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
tk.PhotoImage = tk.Listbox = Widget
for n in ("Frame", "Label", "Combobox", "Button", "Radiobutton", "Checkbutton", "Spinbox", "Entry", "LabelFrame",
          "Progressbar", "Style", "Notebook", "Scale", "Scrollbar"):
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
    shutil.copy(ROOT / "presets" / "Fibo VGL Bionic Gemma12B.json", Path(TMP) / "presets" / "Fibo VGL Bionic Gemma12B.json")
    app.cb_workflow["values"] = [gui.BUILTIN, "fibo2-edit-vgl-bionic-gemma4-12b.json"]
    app.refresh_presets()
    app.load_preset("Fibo VGL Bionic Gemma12B")
    assert app.v_workflow.get() == "fibo2-edit-vgl-bionic-gemma4-12b.json" and app.v_denoise.get() == 1.0
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

    # Turbo LoRA: a switch for workflows that ship a speed LoRA; part of the preset, the request and the state
    wfdir = Path(TMP) / "wf"
    wfdir.mkdir()
    lora_wf = {"1": {"class_type": "UNETLoader", "inputs": {}},
               "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0]}, "_meta": {"title": "pc:lora"}},
               "3": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "steps": 10}, "_meta": {"title": "pc:sampler"}}}
    (wfdir / "turbo.json").write_text(json.dumps(lora_wf), encoding="utf-8")
    shutil.copy(ROOT / "workflows" / "fibo2-edit-plain.json", wfdir / "plain.json")
    app.workflows_dir = wfdir
    app.cb_workflow["values"] = [gui.BUILTIN, "turbo.json", "plain.json"]
    app.v_workflow.set("turbo.json")
    app._on_workflow()
    assert app.cb_turbo["state"] == "normal"
    app.v_turbo.set(False)
    assert app._request().turbo is False
    sd.askstring = lambda *a, **k: "Turbo Off"
    app.save_preset_as()
    t_off = json.loads((Path(TMP) / "presets" / "Turbo Off.json").read_text(encoding="utf-8"))["settings"]
    assert t_off["turbo"] is False and t_off["workflow"] == "turbo.json", t_off
    app.v_turbo.set(True)
    app.load_preset("Turbo Off")
    assert app.v_turbo.get() is False
    app._save_state(app._request())
    assert json.loads((Path(TMP) / "state.json").read_text(encoding="utf-8"))["turbo"] is False
    assert app.cb_turbo["text"] == "LoRA"                 # this test workflow names none
    app.v_workflow.set("plain.json")                      # no speed LoRA there: the switch is greyed out
    app._on_workflow()
    assert app.cb_turbo["state"] == "disabled"
    app.v_preset.set("My Test_")
    print("turbo switch OK")

    # Upscale: a factor box that only the Upscale mode shows; part of the preset, the request and the state
    shown = []
    app.f_scale.pack = lambda *a, **k: shown.append("on")
    app.f_scale.pack_forget = lambda: shown.append("off")
    app.v_mode.set("upscale")
    app._on_mode_ui()
    assert shown[-1] == "on"
    app.v_scale.set("3")
    assert app._request().scale == 3.0 and app._collect()["scale"] == 3.0
    app.v_scale.set("x")                                   # nonsense falls back to 2
    assert app._request().scale == 2.0
    app.v_mode.set("refine")
    app._on_mode_ui()
    assert shown[-1] == "off"
    app.v_mode.set("inpaint")
    app._on_mode_ui()
    print("upscale controls OK")

    # Flux 3 controls: LoRA strength slider, the SeedVR2 stage switch, the detail mix
    shutil.copy(ROOT / "workflows" / "flux3-klein-upscale.json", wfdir / "f3.json")
    app.cb_workflow["values"] = [gui.BUILTIN, "plain.json", "f3.json"]
    app.v_workflow.set("f3.json")
    app.v_turbo.set(True)
    app.v_mode.set("refine")
    app._on_workflow()
    assert app.cb_stage["state"] == "normal" and "SeedVR2" in app.cb_stage["text"] and app.w_lora_str["state"] == "normal"
    assert app.v_lora_str.get() == 1.0
    app.v_lora_str.set(0.4)
    app.v_stage.set(False)
    app.v_detail.set(0.8)
    r = app._request()
    assert r.lora_strength == 0.4 and r.stage_on is False and r.detail == 0.8, (r.lora_strength, r.stage_on, r.detail)
    app.v_workflow.set("plain.json")
    app._on_workflow()
    assert app.cb_stage["state"] == "disabled" and app._request().lora_strength is None and app._request().stage_on is True
    print("flux3 controls OK")

    # comparison series
    assert gui.parse_list("1024, 1224;1536 x", int) == [1024, 1224, 1536] and gui.parse_list("0,2 0.4", float) == [0.0, 2.0, 0.4]
    base = app._request()
    runs = gui.sweep_requests(base, [1024, 1536], [0.2, 0.4])
    assert [(r.base_res, r.context, r.label) for r in runs] == [(1024, 0.2, "res 1024 ctx 0.2"), (1024, 0.4, "res 1024 ctx 0.4"),
                                                                (1536, 0.2, "res 1536 ctx 0.2"), (1536, 0.4, "res 1536 ctx 0.4")]
    assert len(gui.sweep_requests(base, [], [])) == 1 and gui.sweep_requests(base, [], [])[0].label == ""
    print("comparison OK")

    # Mode and workflow go together: Upscale / Refine only with an upscale workflow, the other modes never with one
    shutil.copy(ROOT / "workflows" / "flux3-klein-upscale.json", wfdir / "up.json")
    app.cb_workflow["values"] = [gui.BUILTIN, "turbo.json", "plain.json", "up.json"]
    app.v_workflow.set("plain.json")
    app.v_mode.set("inpaint")
    app._on_mode()
    app.v_mode.set("upscale")
    app._on_mode()
    assert app.v_workflow.get() == "up.json", app.v_workflow.get()       # the mode took the workflow along
    assert app.w_variants["state"] == "disabled" and app.w_denoise["state"] == "disabled"
    assert app.w_adv["Context"]["state"] == "disabled" and app.w_adv["Base res."]["state"] == "disabled"
    assert app.cb_lm["state"] == "disabled"
    assert app.cb_turbo["state"] == "normal" and app.cb_turbo["text"] == "Restore LoRA"   # the upscale workflow's own LoRA
    app.v_mode.set("inpaint")
    app._on_mode()
    assert app.v_workflow.get() == "plain.json", app.v_workflow.get()     # and gave the old one back
    assert app.w_variants["state"] == "normal" and app.w_adv["Context"]["state"] == "normal"
    app.v_workflow.set("up.json")                                          # picking the upscale workflow in the list
    app._workflow_picked()
    assert app.v_mode.get() == "upscale"
    app.v_workflow.set("plain.json")                                       # ... and any other one takes it out again
    app._workflow_picked()
    assert app.v_mode.get() == "inpaint"
    app.v_mode.set("refine")
    app._on_mode()
    assert app.v_workflow.get() == "up.json" and app.cb_lm["state"] == "readonly"   # Refine adds a layer: layer mask stays
    app.v_mode.set("inpaint")
    app._on_mode()
    print("mode/workflow coupling OK")

    # editor keys in the prompt: Ctrl+Left / Ctrl+Right jump by word
    assert gui.word_left("make it night") == 5 and gui.word_left("make it ") == 3 and gui.word_left("") == 0
    assert gui.word_left("make it\n\nnight") == 5 and gui.word_left("red, blue") == 4 and gui.word_left("   ") == 3
    assert gui.word_right("make it night") == 5 and gui.word_right("it, night") == 4 and gui.word_right("night") == 5
    assert gui.word_right("a\n\nb") == 3 and gui.word_right("") == 0 and gui.word_right("  x") == 2
    print("word jumps OK")

    # delete
    app.delete_preset()
    assert not f.exists() and app.v_preset.get() == ""
    print("delete OK")
    print("ALL OK")


if __name__ == "__main__":
    main()
