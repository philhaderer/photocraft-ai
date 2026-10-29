"""The settings overlay, greyed tabs and modes, the click on a greyed tab, the preflight before Generate, linking files,
the extra_model_paths.yaml. Run against the stubbed Tk of test_gui_presets (no display needed).

    python tests/test_settings_ui.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
import test_detection as td  # noqa: E402

gui, cfgmod = t.gui, t.cfgmod
from pccomfy import gui_theme, inventory, manifest, models, ui_settings  # noqa: E402


class RecText(t.Text):
    """The stub Text, but one that takes tags and remembers what it was given."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.parts = []

    def insert(self, idx, s, tags=()):
        self.parts.append((s, tuple(tags)))

    def delete(self, a, b):
        self.parts = []


t.tk.Text = RecText


def make_app():
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    return app


def lists_without(**drop):
    lists = td.full_lists()
    for kind, name in drop.items():
        lists[kind].remove(name.replace("__", "\\"))
    return lists


NODES = {n for tab in manifest.TABS.values() for s in tab.modes.values() for n in s.nodes}


def test_start_state():
    refresh = {"comfy": True}
    full = lambda: inventory.Inventory(td.full_lists(), NODES)       # noqa: E731
    det = lambda inv: {"_detect": True, "_inv": inv, "_yaml": [], "_disk": {}}      # noqa: E731

    # the very first start: no model is chosen, the old "open on the first model" step does not run
    cfgmod.save_state({})
    app = make_app()
    assert app.v_model.get() == "" and app.start_state() == "choose"
    app._apply_refresh(refresh)
    assert app.v_model.get() == "" and app._last_model == "", app.v_model.get()
    app._apply_refresh(det(full()))
    assert app.v_model.get() == "" and app.start_state() == "choose"
    app._apply_refresh(det(inventory.Inventory({})))
    assert app.start_state() == "none_linked" and app.v_model.get() == ""
    # a tab that is not available does not open from the empty state either: its settings do
    app.v_model.set("krea2")
    app._on_model()
    assert app.v_model.get() == "" and app._settings_win is not None and app._settings_focus == "krea2"
    app._settings_close()
    # the first click on a model shows it and remembers it for the next start (state.json)
    app._apply_refresh(det(full()))
    app.v_model.set("flux3")
    app._on_model()
    assert app.v_model.get() == "flux3" and app.start_state() == "" and cfgmod.load_state()["model"] == "flux3"

    # next start: the last model is chosen again (and its mode comes with the saved state)
    cfgmod.save_state({"model": "krea2", "mode": "txt2img", "workflow": "krea2-turbo-t2i.json"})
    app = make_app()
    assert app.v_model.get() == "krea2" and app.v_mode.get() == "txt2img" and app._last_model == "krea2"
    app._apply_refresh(det(full()))
    assert app.v_model.get() == "krea2" and app.start_state() == ""

    # next start, but the last model has lost its files: no tab is chosen, not a broken one; it stays that way
    app = make_app()
    broken = inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES)
    app._apply_refresh(det(broken))
    assert app.v_model.get() == "" and app.v_workflow.get() == gui.BUILTIN and app._last_model == ""
    assert "Krea 2 Turbo is not available" in app.v_status.get() and app.start_state() == "choose"
    app._apply_refresh(refresh)                         # the workflow list is read again: nothing picks the model up again
    assert app.v_model.get() == ""
    app._apply_refresh(det(full()))
    assert app.v_model.get() == ""

    # later in the session a reading that misses a file does not take the tab away from the user
    app.v_model.set("flux3")
    app._on_model()
    app._apply_refresh(det(inventory.Inventory(lists_without(unet="flux3-image-klein-int8-convrot.safetensors"), NODES)))
    assert app.v_model.get() == "flux3"


class Seen:
    """Stands in for a widget and only remembers whether it is packed (the Tk stub does not lay anything out)."""

    def __init__(self):
        self.on = False
        self.fit = 0

    def pack(self, *a, **k):
        self.on = True

    def pack_forget(self):
        self.on = False


def test_empty_view():
    det = lambda inv: {"_detect": True, "_inv": inv, "_yaml": [], "_disk": {}}      # noqa: E731
    cfgmod.save_state({})
    app = make_app()
    shown = {n: Seen() for n in ("f_tabs", "lbl_empty", "f_scrollbox", "lbl_conn", "b_refresh", "b_reset")}
    for n, w in shown.items():
        setattr(app, n, w)
    for n in ("lbl_conn", "b_refresh", "b_reset"):
        shown[n].on = True                                    # the footer starts packed (gui.py)
    on = lambda: {n for n, w in shown.items() if w.on}      # noqa: E731
    all_foot = {"lbl_conn", "b_refresh", "b_reset"}

    app._apply_start_state()
    assert on() == {"f_tabs", "lbl_empty"} | all_foot and app.v_empty.get() == "Choose a function"       # tabs + one sentence + footer, no body
    app._apply_refresh(det(inventory.Inventory({})))
    assert on() == {"lbl_empty"} and app.v_empty.get() == "Link your model in the settings"          # nothing linked: sentence + gear only
    app._apply_refresh(det(inventory.Inventory(td.full_lists(), NODES)))
    assert on() == {"f_tabs", "lbl_empty"} | all_foot
    app.v_model.set("flux3")
    app._on_model()
    assert on() == {"f_tabs", "f_scrollbox"} | all_foot and app.v_empty.get() == ""
    app.v_model.set("")
    app.v_workflow.set("some-own-workflow.json")                  # a workflow of your own is not an empty state
    assert app.start_state() == ""

    # Generate in an empty state does nothing but say so
    called = []
    gui.RunMixin.generate = lambda self: called.append(1)
    app.v_workflow.set(gui.BUILTIN)
    assert app.start_state() == "choose"
    app.generate()
    assert called == [] and app.v_status.get() == "Choose a function first."
    print("ok empty view")


def main():
    # the gear sits in the footer row, in the same frame as the refresh arrow and "Defaults" (not next to the tabs)
    made = []

    class RecBtn(t.Widget):
        def __init__(self, master=None, **k):
            super().__init__(master, **k)
            self.master = master
            self.text = k.get("text")
            self.image = k.get("image")
            made.append(self)

    plain = t.ttk.Button
    t.ttk.Button = RecBtn
    probe = gui.App(cfgmod.load())
    t.ttk.Button = plain
    assert probe.b_gear.master is not probe.f_tabs and probe.b_gear.image == probe._icon("gear", px=ui_settings.GEAR_PX) and probe.b_gear.master is not None
    foot = [b.master for b in made if b.text == "Defaults" or b.image == probe._icon("refresh", px=ui_settings.GEAR_PX)]
    assert len(foot) == 2 and foot[0] is foot[1] and probe.b_gear.master is foot[0]
    # flat like the trash button (no dark button background) and about 60 % of the other icons (user 28.10.)
    assert probe.b_gear["style"] == probe.b_clear["style"] == "Link.TButton" and ui_settings.GEAR_PX == 12 == round(0.6 * gui_theme.ICON_PX)
    # Refresh = a flat circle arrow in the gear's size, Reset = the text link "Defaults" (option A, user 29.10.)
    assert probe.b_refresh.image == probe._icon("refresh", px=ui_settings.GEAR_PX) and probe.b_refresh.text is None
    assert probe.b_reset.text == "Defaults" and probe.b_refresh["style"] == probe.b_reset["style"] == "Link.TButton"
    # the prompt field scrolls with the thin bar, shown by itself only while the text is longer than the field (29.10.)
    assert isinstance(probe.sb_prompt, gui.ThinScrollbar) and probe.sb_prompt.auto and probe.sb_prompt.canvas is probe.t_prompt
    del probe

    app = make_app()

    # the hooks: SettingsMixin first, a gear button, a tooltip object per tab
    assert gui.App.__mro__[1].__name__ == "SettingsMixin"
    assert app.b_gear is not None and set(app.tt_tabs) == {m.key for m in models.MODELS}
    assert app.inv is None
    app.v_model.set("flux3")
    app.v_mode.set("edit")
    app._on_model()
    assert app.v_model.get() == "flux3" and app._last_model == "flux3"
    assert all(app.rb_modes[k]["state"] == "normal" for k in models.FLUX3.modes)    # functions are never greyed
    assert [k for k, rb in app.rb_tabs.items() if rb["state"] == "normal"] == [m.key for m in models.MODELS if "edit" in m.modes]   # models that cannot edit are

    # a full install: nothing is grey, no extra tooltip text
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES), "_yaml": [], "_disk": {}})
    assert all(rb["style"] == "Chip.Toolbutton" for rb in app.rb_tabs.values())
    assert app.tt_tabs["flux3"].text == models.FLUX3.tip
    assert app.comfy.name_fixer is not None
    assert app._preflight() == []

    # SeedVR2 missing: Flux 3 stays a normal chip for Edit; for Upscale its chip turns red, the tooltip says why
    inv = inventory.Inventory(lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), NODES)
    app._apply_refresh({"_detect": True, "_inv": inv, "_yaml": [], "_disk": {}})
    assert app.rb_tabs["flux3"]["style"] == "Chip.Toolbutton"
    assert app.rb_modes["upscale"]["state"] == "normal" and app.rb_modes["edit"]["state"] == "normal"
    app.v_mode.set("upscale"); app._update_mode_radios()
    assert app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton" and app.rb_tabs["qwen"]["state"] == "disabled"
    app.v_mode.set("edit"); app._update_mode_radios()
    assert "Missing for Upscale (new file): seedvr2_3b_int8_convrot.safetensors. Set in settings" in app.tt_modes["upscale"].text
    assert app.tt_modes["upscale"].text.startswith(models.function_tip("upscale", models.FUNCTION_TIPS["upscale"]))
    assert "Missing for Upscale" in app.tt_tabs["flux3"].text and app.tt_tabs["flux3"].text.startswith(models.FLUX3.tip)
    app._update_mode_radios()          # called again (a tab switch does that): the tooltip does not grow
    assert app.tt_modes["upscale"].text.count("Missing for") == 1

    # Krea 2's VAE missing: the tab is grey, its tooltip says what; the Flux 3 tab is still the selected one
    inv = inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES)
    app._apply_refresh({"_detect": True, "_inv": inv, "_yaml": [], "_disk": {}})
    assert app.rb_tabs["krea2"]["style"] == "Missing.Chip.Toolbutton" and app.rb_tabs["flux3"]["style"] == "Chip.Toolbutton"
    assert app.tt_tabs["krea2"].text == models.KREA2.tip + "\n\nMissing: qwen_image_vae.safetensors. Set in settings (gear)."
    assert app.rb_modes["upscale"]["state"] == "normal"            # the SeedVR2 problem is gone with the new reading

    # a click on the grey tab opens the settings instead of switching
    app.v_model.set("krea2")
    app._on_model()
    assert app.v_model.get() == "flux3" and app._last_model == "flux3"
    assert app._settings_win is not None and app._settings_focus == "krea2"
    text = "".join(p for p, _tags in app.t_settings.parts)
    assert "Installed models" in text and "Credits" not in text and "\u25C0" in text
    assert "Credits" in "".join(p for p, _tags in app.t_credits.parts)          # the second tab of the settings window
    assert "\u2717 qwen_image_vae.safetensors" in text and "ComfyUI\\models\\vae" in text
    assert not hasattr(app, "lbl_set_dot")                 # no ComfyUI dot in the settings window (the footer has it)
    app._settings_close()
    assert app._settings_win is None

    # the preflight stops the run with one clear line; the model is not Flux 3 any more
    called = []
    gui.RunMixin.generate = lambda self: called.append(self.v_model.get())
    app.v_model.set("krea2")
    app._last_model = "krea2"
    app.v_mode.set("txt2img")
    app.comfy = td.FakeComfy(lists_without(vae="qwen_image_vae.safetensors"))
    app.generate()
    assert called == [] and app.v_status.get().startswith("Krea 2 Turbo: missing: qwen_image_vae.safetensors -> ComfyUI\\models\\vae"), app.v_status.get()
    assert "Restart ComfyUI" in app.v_status.get()

    # the cached reading is old: the file was copied and ComfyUI restarted. One fresh look lets the run through
    app.comfy = td.FakeComfy(td.full_lists())
    app.generate()
    assert called == ["krea2"] and app.rb_tabs["krea2"]["style"] == "Chip.Toolbutton" and app.inv.tab_status("krea2").state == "ready"

    # a workflow of your own (no tab) and an unreachable ComfyUI never stop a run
    app.v_model.set("")
    app.generate()
    assert called == ["krea2", ""]
    app._apply_refresh({"_detect": True, "_inv": None, "_inv_error": "No connection to ComfyUI", "_yaml": [], "_disk": {}})
    assert app.inv is None and app.comfy.name_fixer is None and all(rb["style"] == "Chip.Toolbutton" for rb in app.rb_tabs.values())
    app.v_model.set("krea2")
    app.generate()
    assert called == ["krea2", "", "krea2"]
    app.open_settings()
    text = "".join(p for p, _tags in app.t_settings.parts)
    assert "ComfyUI could not be read." in text and "No connection to ComfyUI" in text
    app._settings_close()
    # the gear toggles: a click opens the window, the next one closes it (user 28.10.)
    assert app.b_gear["command"] == app.toggle_settings and app._settings_win is None
    app.toggle_settings()
    win = app._settings_win
    assert win is not None
    closed = []
    win.destroy = lambda: closed.append(True)
    win.winfo_exists = lambda: 1
    app.toggle_settings()
    assert closed == [True] and app._settings_win is None
    app.toggle_settings()
    assert app._settings_win is not None and app._settings_win is not win
    app._settings_close()

    # the overlay text: downloads are links, a missing node names its pack, the credits are links
    inv = inventory.Inventory(lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), {"SeedVR2Preprocess"})
    app._apply_refresh({"_detect": True, "_inv": inv, "_yaml": [], "_disk": {"seedvr2_3b_int8_convrot.safetensors": ["D:/models/diffusion_models/seedvr2_3b_int8_convrot.safetensors"]}})
    seg = app._settings_segments() + app._credits_segments()
    links = [u for _t, style, u in seg if style == "link"]
    assert manifest.FILES["seedvr2_3b_int8_convrot.safetensors"].url in links and "(3.5 GB)" in "".join(s for s, _st, _u in seg) and "https://github.com/ausboss/ComfyUI-AusBoss" in links
    assert all(u.startswith("https://") for u in links) and len(links) >= len(manifest.CONTRIBUTORS)
    joined = "".join(s for s, _st, _u in seg)
    assert "node AUSBOSS_NODES_TiledUpscale" in joined and "found on disk: D:/models/diffusion_models/seedvr2" in joined
    assert "Peszemeszek" in joined and "optional" in joined and "(as " not in joined

    # link a file of another name: the tab turns ready at once and graphs get the real name
    lists = td.full_lists()
    lists["vae"].remove("flux2-vae.safetensors")
    lists["vae"].append("my_vae.safetensors")
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists, NODES), "_yaml": [], "_disk": {}})
    assert app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton" and app.rb_tabs["fibo"]["style"] == "Missing.Chip.Toolbutton"
    app.open_settings()
    exp, avail = app._link_choices()
    assert "flux2-vae.safetensors" in exp and "my_vae.safetensors" in avail["vae"]
    # "Choose another file..." next to every file (found or missing): it sets the boxes to that file
    picks = [u for _t, style, u in app._settings_segments() if style == "pick"]
    assert picks and set(picks) == set(exp), (len(picks), len(exp))
    assert all(t == "Choose another file…" for t, style, _u in app._settings_segments() if style == "pick")
    app._choose_for("flux2-vae.safetensors")
    assert app.v_link_exp.get() == "flux2-vae.safetensors" and "my_vae.safetensors" in app.cb_link_act["values"]
    app.v_link_exp.set("flux2-vae.safetensors")
    app._link_expected_picked()
    assert "my_vae.safetensors" in app.cb_link_act["values"] and "flux3-image-klein-int8-convrot.safetensors" not in app.cb_link_act["values"]
    assert app.cb_link_act["values"][0] == "flux2-vae.safetensors" and app.v_link_cur.get() == "missing"
    app.v_link_act.set("my_vae.safetensors")
    assert cfgmod.model_map() == {}                       # choosing alone changes nothing: only "Relink" does
    app._link_models()
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors"}
    assert app.v_link_cur.get() == "my_vae.safetensors  (linked)" and app.b_link_undo["state"] == "normal"
    app._link_undo()                                      # Undo: back to no link
    assert cfgmod.model_map() == {} and app.b_link_undo["state"] == "disabled"
    app.v_link_act.set("my_vae.safetensors")
    app._link_models()
    app._link_reset()                                     # Reset: the links of the start (none here)
    assert cfgmod.model_map() == {} and app.b_link_reset["state"] == "disabled"
    assert app.b_link_undo["state"] == "disabled"        # Undo takes back relinks only, not the reset
    app.v_link_act.set("my_vae.safetensors")
    app._link_models()
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors"}
    assert "flux2-vae.safetensors  (your file: my_vae.safetensors)" in "".join(s for s, _st, _u in app._settings_segments())
    assert app.rb_tabs["flux3"]["style"] == "Chip.Toolbutton" and app.inv.tab_status("flux3").state == "ready"
    g = {"1": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}}
    app.comfy.name_fixer(g)
    assert g["1"]["inputs"]["vae_name"] == "my_vae.safetensors"
    assert "flux2-vae.safetensors  \u2192  my_vae.safetensors" in "".join(s for s, _st, _u in app._settings_segments())
    app.v_link_exp.set("flux2-vae.safetensors")
    app._unlink_model()
    assert cfgmod.model_map() == {} and app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton"
    app._link_models()          # nothing chosen below: nothing happens
    app._settings_close()

    # extra_model_paths.yaml: choosing a file reads it in a thread and the result arrives as an event
    base = Path(tempfile.mkdtemp())
    (base / "models" / "vae").mkdir(parents=True)
    (base / "models" / "vae" / "flux2-vae.safetensors").write_bytes(b"")
    ypath = base / "extra_model_paths.yaml"
    ypath.write_text(f"comfyui:\n    base_path: {base.as_posix()}\n    vae: models/vae\n", encoding="utf-8")
    app.settings_set_yaml(str(ypath))
    assert cfgmod.extra_paths_file() == str(ypath)
    kind, data = app.events.get(timeout=10)
    assert kind == "refresh" and data["_detect"] and "_inv" not in data
    app._apply_refresh(data)
    assert app._yaml_sections[0]["folders"]["vae"] == [(base / "models" / "vae").as_posix()]
    joined = "".join(s for s, _st, _u in app._settings_segments())
    assert str(ypath) in joined and "found on disk:" in joined and "restart ComfyUI to list it" in joined
    app.settings_set_yaml("")
    kind, data = app.events.get(timeout=10)
    app._apply_refresh(data)
    assert cfgmod.extra_paths_file() == "" and app._yaml_sections == [] and "No file chosen" in "".join(s for s, _st, _u in app._settings_segments())

    # the settings window is an owned window of the bridge window (hidden / minimised / closed with it), never "always on top"
    class RecWin(t.Widget):
        calls = []

        def attributes(self, *a, **k):
            RecWin.calls.append(a)

    class FakeApi:
        owners = {}

        def toplevel(self, w):
            return id(w) % 100000 + 1

        def owner_of(self, hwnd):
            return FakeApi.owners.get(hwnd, 0)

        def set_owner(self, hwnd, owner):
            FakeApi.owners[hwnd] = owner

    saved = (t.tk.Toplevel, gui.winlink.available, gui.winlink.Win32Api)
    t.tk.Toplevel, gui.winlink.available, gui.winlink.Win32Api = RecWin, (lambda: True), FakeApi
    try:
        app._settings_win = None
        app.open_settings()
        assert not any("-topmost" in c for c in RecWin.calls), RecWin.calls
        assert FakeApi.owners == {FakeApi().toplevel(app._settings_win): FakeApi().toplevel(app.root)}, FakeApi.owners
        app._settings_close()
        gui.winlink.available = lambda: False          # not Windows: nothing is owned, nothing breaks
        FakeApi.owners.clear()
        app.open_settings()
        assert FakeApi.owners == {}
        app._settings_close()
    finally:
        t.tk.Toplevel, gui.winlink.available, gui.winlink.Win32Api = saved

    # a preset that needs a model with missing files says so (the loader uses this; see docs/entscheidungen-L1.md)
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES), "_yaml": [], "_disk": {}})
    note = app.preset_blocked({"workflow": "krea2-turbo-t2i.json", "mode": "txt2img"})
    assert note == "Krea 2 Turbo is missing files: qwen_image_vae.safetensors (see settings)", note
    assert app.preset_blocked({"workflow": "flux3-klein-edit.json", "mode": "edit"}) == ""
    assert app.preset_blocked({"workflow": gui.BUILTIN}) == "" and app.preset_blocked({}) == "" and app.preset_blocked({"workflow": "my own.json"}) == ""
    # loading such a preset keeps the current tab and mode and says what is missing (the loader in gui_state.py)
    import json as _json
    pp = app._preset_path("blocked")
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(_json.dumps({"settings": {"workflow": "krea2-turbo-t2i.json", "mode": "txt2img", "model": "krea2"}}), encoding="utf-8")
    app.v_model.set("flux3"); app.v_mode.set("edit"); app.v_workflow.set("flux3-klein-edit.json")      # a consistent state to come back to
    before = (app.v_model.get(), app.v_mode.get(), app.v_workflow.get())
    app.load_preset("blocked")
    assert (app.v_model.get(), app.v_mode.get(), app.v_workflow.get()) == before, before
    assert "Not applied: Krea 2 Turbo is missing files: qwen_image_vae.safetensors" in app.v_status.get(), app.v_status.get()
    pp.unlink()
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), NODES), "_yaml": [], "_disk": {}})
    assert app.preset_blocked({"workflow": "flux3-klein-upscale.json", "mode": "upscale"}).startswith("Flux 3 Klein Edit is missing files: seedvr2_3b")
    assert app.preset_blocked({"workflow": "flux3-klein-edit.json", "mode": "edit"}) == ""      # the same tab, another mode: fine
    app._apply_refresh({"_detect": True, "_inv": None, "_inv_error": "x", "_yaml": [], "_disk": {}})
    assert app.preset_blocked({"workflow": "krea2-turbo-t2i.json", "mode": "txt2img"}) == ""

    # a normal PhotoCraft/ComfyUI refresh still goes through the old path
    app._apply_refresh({"comfy": True})
    assert app.v_conn.get() == "ComfyUI connected" and app.lbl_dot.cget("style") == "ConnOk.TLabel"
    app._apply_refresh({"comfy": False})
    assert app.v_conn.get() == "ComfyUI not connected" and app.lbl_dot.cget("style") == "ConnBad.TLabel"
    test_start_state()
    test_empty_view()
    print("ok")


if __name__ == "__main__":
    main()
