"""The last 20 runs (PLAN point 13, user 30.10.): the clock in the header lists finished runs; a click loads every setting
with a new seed and starts nothing; when the text model wrote the prompt, that text comes back with Enhance off. The
history file on its own, then the window against the Tk stub.

    python tests/test_run_history.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
from pccomfy import history  # noqa: E402

gui, cfgmod = t.gui, t.cfgmod


def file_checks():
    f = Path(tempfile.mkdtemp()) / "history.json"
    assert history.load(f) == []                                             # no file yet
    for i in range(25):
        history.add(f, history.entry(f"Edit {i}", "Flux 2", {"prompt": f"p{i}", "seed": 7}))
    runs = history.load(f)
    assert len(runs) == 20 and runs[0]["title"] == "Edit 24" and runs[-1]["title"] == "Edit 5"   # newest first, 20 kept
    f.write_text("{broken", encoding="utf-8")
    assert history.load(f) == []                                             # a broken file is an empty list

    e = history.entry("Fill Selection 3", "Fibo 2.0", {"prompt": "a red flower in a vase on the table by the window, "
                                                                 "soft morning light", "seed": 42, "enhance": True})
    e["time"] = "2026-10-30 14:22"
    assert history.label(e, today="2026-10-30") == "14:22  Fill Selection 3 · Fibo 2.0: a red flower in a vase on the table by the…"
    assert history.label(e, today="2026-10-31").startswith("30 Oct 14:22  Fill Selection 3")
    s = history.settings_to_load(e)
    assert s["seed"] == -1 and s["enhance"] is True and s["prompt"].startswith("a red flower")     # no LLM text: own prompt
    e["llm"] = "A vivid red tulip"
    s = history.settings_to_load(e)
    assert s["prompt"] == "A vivid red tulip" and s["enhance"] is False and s["seed"] == -1
    assert e["settings"]["seed"] == 42                                       # the saved run itself stays as it was
    assert history.label(e, today="2026-10-30").endswith(": A vivid red tulip")


class Menu:
    def __init__(self):
        self.items = []

    def delete(self, *a):
        self.items = []

    def add_command(self, label="", command=None, state="normal"):
        self.items.append((label, command, state))

    def tk_popup(self, *a):
        pass

    def grab_release(self):
        pass


def gui_checks():
    cfgmod.HISTORY_FILE = Path(tempfile.mkdtemp()) / "history.json"
    app = gui.App(cfgmod.load())
    app.cb_workflow["values"] = [gui.BUILTIN, "fibo2-edit.json", "fibo2-edit-both.group.json"]
    app.m_history = Menu()
    app.b_history.winfo_rootx = app.b_history.winfo_rooty = app.b_history.winfo_height = lambda: 0

    app._history_menu()                                                      # nothing run yet
    assert app.m_history.items == [("No runs yet.", None, "disabled")]

    # a run: Fill with Fibo, the text model rewrites the prompt
    app.v_mode.set("inpaint")
    app.v_workflow.set("fibo2-edit.json")
    app._sync_model()
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a red flower")
    app.t_neg.delete("1.0", "end")
    app.t_neg.insert("1.0", "blurry")
    app.v_enhance.set(True)
    app.v_seed.set(1234)
    app.v_variants.set(3)
    app.v_feather.set(6.5)
    req = app._request()
    req.group_name = "Fill Selection 3"
    app._history_begin(req)
    app.events.put(("vgl", "A vivid red tulip in full bloom"))
    app.events.put(("done", "Done · seed 1234 · created 3 layers · 9 s"))
    app._poll()
    runs = history.load(cfgmod.HISTORY_FILE)
    assert len(runs) == 1 and runs[0]["title"] == "Fill Selection 3" and runs[0]["llm"] == "A vivid red tulip in full bloom"
    assert runs[0]["settings"]["seed"] == 1234 and runs[0]["settings"]["prompt"] == "a red flower"

    # a cancelled and a failed run are not kept
    for done in ("Cancelled.", "Error: ComfyUI is not running"):
        app._history_begin(req)
        app.events.put(("done", done))
        app._poll()
    assert len(history.load(cfgmod.HISTORY_FILE)) == 1

    # change everything, then load the run from the menu
    app.v_mode.set("edit")
    app.v_workflow.set(gui.BUILTIN)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "something else")
    app.t_neg.delete("1.0", "end")
    app.v_variants.set(1)
    app.v_feather.set(2.0)
    app._history_menu()
    (label, command, state), = app.m_history.items
    assert "Fill Selection 3" in label and state == "normal", label
    command()
    assert app.v_mode.get() == "inpaint" and app.v_workflow.get() == "fibo2-edit.json"
    assert app.v_variants.get() == 3 and abs(app.v_feather.get() - 6.5) < 1e-6
    assert app.v_seed.get() == -1                                            # a new seed
    assert app.t_prompt.get("1.0", "end").strip() == "A vivid red tulip in full bloom" and app.v_enhance.get() is False
    assert app.t_neg.get("1.0", "end").strip() == "blurry"
    assert "Loaded “Fill Selection 3”" in app.v_status.get() and app.worker is None    # nothing started
    json.loads(cfgmod.HISTORY_FILE.read_text(encoding="utf-8"))              # still a valid file


def main():
    file_checks()
    gui_checks()
    print("test_run_history: ok")


if __name__ == "__main__":
    main()
