"""The settings overlay, greyed tabs and modes, the click on a greyed tab, the preflight before Generate, linking files. Run against the stubbed Tk of test_gui_presets (no display needed).

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


def rows_text(app) -> str:
    """The "Models" tab of the settings window as one text (its rows, as _settings_draw shows them)."""
    out = []
    for row in app._settings_rows():
        kind = row[0]
        if kind == "model":
            out.append(f"{row[2]}  {ui_settings.STATE_TEXT[row[3]]}" + ("  \u25C0" if row[4] else ""))
        elif kind == "file":
            d = row[1]
            out.append(("\u2713 " if d["found"] is not None else "\u2717 ") + d["path"] + ("  (optional)" if d["level"] == "optional" else "")
                       + (f"  (your file: {d['found']})" if d["found"] not in (None, d["name"]) else "")
                       + (f"  {d['size']}" if d["size"] else "") + (f"  {d['note']}" if d["note"] else "")
)
        elif kind == "node":
            out.append(f"node {row[1]}  {row[2]}")
        elif kind == "error":
            out.append(row[1] + "\n" + row[2])
        elif kind not in ("sep", "stop"):   # the light lines and the "Stop downloads" buttons carry no text
            out.append(row[1])
    return "\n".join(out)


def file_rows(app) -> list[dict]:
    return [row[1] for row in app._settings_rows() if row[0] == "file"]


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
    det = lambda inv: {"_detect": True, "_inv": inv}      # noqa: E731

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
    # no model linked: no "Live preview" tick and no idle "Ready" (user 2.11.)
    assert app._live_shown is False and app.v_status.get() == ""
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
    assert app._live_shown and app.v_status.get() == "Ready"      # back with a model

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
    det = lambda inv: {"_detect": True, "_inv": inv}      # noqa: E731
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
    assert on() == {"f_tabs", "lbl_empty"} | all_foot and app.v_empty.get() == "Choose a model"       # tabs + one sentence + footer, no body
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
    assert called == [] and app.v_status.get() == "Choose a model first."
    print("ok empty view")


def test_other_settings():
    """Tab "Other settings" (user 1.11.): "Show all hidden models" and "Reset all modes to default settings"."""
    cfgmod.save_state({})
    app = make_app()
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES)})
    cfgmod.set_setting("hidden_tabs", None)
    app._show_hidden_models()
    assert "No model is hidden" in app.v_status.get()
    cfgmod.set_tab_hidden("fibo", True)
    cfgmod.set_tab_hidden("qwen", True)
    app._show_hidden_models()
    assert cfgmod.hidden_tabs() == set() and "2 hidden models shown again" in app.v_status.get(), app.v_status.get()

    cfgmod.set_setting("saved_pages", None)
    app._reset_all_modes()
    assert "No page has saved settings" in app.v_status.get()
    cfgmod.set_saved_page("flux3", "txt2img", {"steps": 5})
    cfgmod.set_saved_page("fibo", "edit", {"steps": 7})
    saved_ask = ui_settings.messagebox.askyesno
    ui_settings.messagebox.askyesno = lambda *a, **k: False            # "No": everything stays
    app._reset_all_modes()
    assert cfgmod.saved_page("flux3", "txt2img") == {"steps": 5}
    ui_settings.messagebox.askyesno = lambda *a, **k: True
    try:
        app._reset_all_modes()
    finally:
        ui_settings.messagebox.askyesno = saved_ask
    assert cfgmod.saved_page("flux3", "txt2img") == {} and cfgmod.saved_page("fibo", "edit") == {}
    assert "standard settings" in app.v_status.get()


def test_page_layout_and_stop():
    """Each model page: the files the standard settings need first, a line, then the extra-feature files under their own heading
    (user 2.11.); a "Stop downloads" row ends every page; "Download needed models" leaves out what is loaded already."""
    app = make_app()
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES)})
    rows = app._settings_rows()
    heads = [r[1] for r in rows if r[0] == "head"]
    assert "Needs these weights:" not in heads and heads.count("Standard settings need these weights:") == len(models.MODELS)
    assert ui_settings.OPTIONAL_HEAD == "These models are only needed for additional features:" and ui_settings.OPTIONAL_HEAD in heads
    i = rows.index(("head", ui_settings.OPTIONAL_HEAD))
    assert rows[i - 1] == ("sep",)                                    # the line between needed and optional
    stops = [r for r in rows if r[0] == "stop"]
    assert len(stops) == len(models.MODELS) + 1 and rows[-1][0] == "stop"       # one per model page and one for "Additional"
    # within a model page every file before the optional heading is required, every one after it is not
    flux = [r for r in rows if r[0] == "file"]
    assert not any("optional, not used" in str(r) for r in rows)
    # a file loaded in this session (ComfyUI lists it only after a restart) is no longer counted as missing
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES)})
    before = next(r for r in app._settings_rows() if r[0] == "model" and r[1] == "krea2")[5]
    assert before and before["count"] >= 1
    app._dl_restart.add("qwen_image_vae.safetensors")
    after = next(r for r in app._settings_rows() if r[0] == "model" and r[1] == "krea2")[5]
    assert after is None or after["count"] == before["count"] - 1, (before, after)
    # "Stop downloads" cancels only the running ones of its page
    ev = {}
    app._dl["a.safetensors"] = {"cancel": type("E", (), {"set": lambda self: ev.setdefault("a", True)})()}
    app.download_cancel_all(["a.safetensors", "b.safetensors"])
    assert ev == {"a": True}


def main():
    # the gear sits in the footer row, in the same frame as the refresh arrow and "Reset page" (not next to the tabs)
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
    foot = [b.master for b in made if b.text == "Reset page" or b.image == probe._icon("refresh", px=ui_settings.GEAR_PX)]
    assert len(foot) == 2 and foot[0] is foot[1] and probe.b_gear.master is foot[0]
    # flat like the trash button (no dark button background) and about 60 % of the other icons (user 28.10.)
    assert probe.b_gear["style"] == probe.b_clear["style"] == "Link.TButton" and ui_settings.GEAR_PX == 12 == round(0.6 * gui_theme.ICON_PX)
    # Refresh = a flat circle arrow in the gear's size, Reset = the small button "Reset page" (option A, user 29.10.)
    assert probe.b_refresh.image == probe._icon("refresh", px=ui_settings.GEAR_PX) and probe.b_refresh.text is None
    assert probe.b_reset.text == "Reset page" and probe.b_refresh["style"] == "Link.TButton" and probe.b_reset["style"] == "Small.TButton"
    # the prompt field scrolls with the thin bar, shown by itself only while the text is longer than the field (29.10.)
    assert isinstance(probe.sb_prompt, gui.ThinScrollbar) and probe.sb_prompt.auto and probe.sb_prompt.canvas is probe.t_prompt
    del probe

    app = make_app()

    # the hooks: SettingsMixin first, a gear button, a tooltip object per tab
    assert gui.App.__mro__[1].__name__ == "EasyMixin" and gui.App.__mro__[2].__name__ == "SettingsMixin"
    assert app.b_gear is not None and set(app.tt_tabs) == {m.key for m in models.MODELS}
    assert app.inv is None
    app.v_model.set("flux3")
    app.v_mode.set("edit")
    app._on_model()
    assert app.v_model.get() == "flux3" and app._last_model == "flux3"
    assert all(app.rb_modes[k]["state"] == "normal" for k in models.FLUX3.modes)    # functions are never greyed
    assert [k for k, rb in app.rb_tabs.items() if rb["state"] == "normal"] == [m.key for m in models.MODELS if "edit" in m.modes]   # models that cannot edit are

    # a full install: nothing is grey, no extra tooltip text
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES)})
    assert all(rb["style"] == "Chip.Toolbutton" for rb in app.rb_tabs.values())
    assert app.tt_tabs["flux3"].text == models.FLUX3.tip
    assert app.comfy.name_fixer is not None
    assert app._preflight() == []

    # the Restore LoRA missing: one function lacks the files of its standard settings, so the whole model is locked (red chip
    # for every function, user 30.10.); its tooltip says which function needs what
    inv = inventory.Inventory(lists_without(lora="Flux 3__flux-3-image-klein-restore.safetensors"), NODES)
    app._apply_refresh({"_detect": True, "_inv": inv})
    assert app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton" and inv.tab_status("flux3").state == "missing"
    assert app.rb_modes["upscale"]["state"] == "normal" and app.rb_modes["edit"]["state"] == "normal"
    app.v_mode.set("upscale"); app._update_mode_radios()
    assert app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton" and app.rb_tabs["qwen"]["state"] == "normal"      # Qwen can upscale too (2.11.)
    app.v_mode.set("edit"); app._update_mode_radios()
    assert "Missing for Upscale (new file): Flux 3\\flux-3-image-klein-restore.safetensors. Set in settings" in app.tt_modes["upscale"].text
    assert app.tt_modes["upscale"].text.startswith(models.function_tip("upscale", models.FUNCTION_TIPS["upscale"]))
    assert "Missing for Upscale" in app.tt_tabs["flux3"].text and app.tt_tabs["flux3"].text.startswith(models.FLUX3.tip)
    app._update_mode_radios()          # called again (a tab switch does that): the tooltip does not grow
    assert app.tt_modes["upscale"].text.count("Missing for") == 1

    # Krea 2's VAE missing: the tab is grey, its tooltip says what; the Flux 3 tab is still the selected one
    inv = inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES)
    app._apply_refresh({"_detect": True, "_inv": inv})
    assert app.rb_tabs["krea2"]["style"] == "Missing.Chip.Toolbutton" and app.rb_tabs["flux3"]["style"] == "Chip.Toolbutton"
    assert app.tt_tabs["krea2"].text == models.KREA2.tip + "\n\nMissing: qwen_image_vae.safetensors. Set in settings (gear)."
    assert app.rb_modes["upscale"]["state"] == "normal"            # the SeedVR2 problem is gone with the new reading

    # a click on the grey tab opens the settings instead of switching
    app.v_model.set("krea2")
    app._on_model()
    assert app.v_model.get() == "flux3" and app._last_model == "flux3"
    assert app._settings_win is not None and app._settings_focus == "krea2"
    text = rows_text(app)
    assert "restart ComfyUI" in text and "Credits" not in text and "Krea 2 Turbo  is not yet available  \u25C0" in text
    assert "Credits" in "".join(p for p, _tags in app.t_credits.parts)          # the second tab of the settings window
    assert "\u2717 /vae/qwen_image_vae.safetensors" in text          # the path with its folder (user 30.10.)
    assert "\u2713 /loras/Flux 3/flux-3-image-klein-restore.safetensors" in text
    assert app._settings_size() == (app._px(ui_settings.SETTINGS_W), app._px(ui_settings.SETTINGS_H))   # wider at first
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
    app._apply_refresh({"_detect": True, "_inv": None, "_inv_error": "No connection to ComfyUI"})
    assert app.inv is None and app.comfy.name_fixer is None and all(rb["style"] == "Chip.Toolbutton" for rb in app.rb_tabs.values())
    app.v_model.set("krea2")
    app.generate()
    assert called == ["krea2", "", "krea2"]
    app.open_settings()
    text = rows_text(app)
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
    win.winfo_width, win.winfo_height = (lambda: 900), (lambda: 640)     # the size you gave it ...
    app.toggle_settings()
    assert closed == [True] and app._settings_win is None
    assert cfgmod.get_setting("settings_size") == [900, 640] and app._settings_size() == (900, 640)   # ... comes back
    app.toggle_settings()
    assert app._settings_win is not None and app._settings_win is not win
    app._settings_close()

    # the rows: a missing file has its download link and size, a missing node names its pack, the credits are links
    inv = inventory.Inventory(lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), {"SomethingElse"})
    app._apply_refresh({"_detect": True, "_inv": inv})
    seed = next(d for d in file_rows(app) if d["name"] == "seedvr2_3b_int8_convrot.safetensors")
    assert seed["url"] == manifest.FILES[seed["name"]].url and seed["size"] == "3.5 GB" and seed["path"] == "/diffusion_models/" + seed["name"]
    nodes = [row for row in app._settings_rows() if row[0] == "node"]
    assert not any(n[1].startswith("AUSBOSS_NODES_") for n in nodes)          # Flux 3 Upscale needs no AusBoss nodes any more (2.11.)
    # BiRefNet and the preview decoders stand once, under "Additional models", with what they are for (user 30.10.)
    extra = {d["name"]: d for d in file_rows(app) if d.get("use")}
    assert set(extra) == {n for n, f in manifest.FILES.items() if f.kind in ("bg_removal", "preview")}, set(extra)
    assert extra["birefnet.safetensors"]["use"] == "Cut out in Multi Image Edit: Flux 3, Flux 2, Qwen, Fibo"
    assert extra["taef2_decoder.pth"]["use"] == "Live preview: Flux 3, Flux 2, Fibo, MOSS"
    assert sum(d["name"] == "taef2_decoder.pth" for d in file_rows(app)) == 1          # not again under each model
    assert "Additional models (used by several models)" in rows_text(app)
    links = [u for _t, style, u in app._credits_segments() if style == "link"]
    assert all(u.startswith("https://") for u in links) and len(links) >= len(manifest.CONTRIBUTORS)
    joined = rows_text(app) + "".join(s for s, _st, _u in app._credits_segments())
    assert "Peszemeszek" in joined and "optional" in joined and "(as " not in joined

    # Live preview: off and greyed out while the model's preview decoder is missing, on again once it is there (user 30.10.)
    app.v_model.set("flux3")
    app._last_model = "flux3"
    app._on_model()
    assert app.v_live.get() is True and app.cb_live["state"] == "normal"
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists_without(preview="taef2_decoder.pth"), NODES)})
    assert app.v_live.get() is False and app.cb_live["state"] == "disabled" and "taef2_decoder.pth" in app.tt_live.text
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES)})
    assert app.v_live.get() is True and app.cb_live["state"] == "normal" and app.tt_live.text == gui.LIVE_TIP

    # link a file of another name: the tab turns ready at once and graphs get the real name
    lists = td.full_lists()
    lists["vae"].remove("flux2-vae.safetensors")
    lists["vae"].append("my_vae.safetensors")
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists, NODES)})
    assert app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton" and app.rb_tabs["fibo"]["style"] == "Missing.Chip.Toolbutton"
    app.open_settings()
    # the chain next to every file (found or missing) lists the other files of its kind, the most similar name first
    cands = app._link_candidates("flux2-vae.safetensors")
    assert "my_vae.safetensors" in cands and "flux3-image-klein-int8-convrot.safetensors" not in cands
    assert "flux2-vae.safetensors" not in cands and cands[0] == "flux2-vae_small.safetensors", cands     # the nearest name first
    assert "qwen_image_vae.safetensors" in cands and "qwen_image_vae.safetensors" not in app._link_candidates("qwen_image_vae.safetensors")
    assert app._link_candidates("no-such-file") == []
    app._link_models("flux2-vae.safetensors", "my_vae.safetensors")       # one click on an entry links at once
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors"} and app.b_link_undo["state"] == "normal"
    app._link_undo()                                      # Undo: back to no link
    assert cfgmod.model_map() == {} and app.b_link_undo["state"] == "disabled"
    app._link_models("flux2-vae.safetensors", "my_vae.safetensors")
    app._link_reset()                                     # Reset: the links of the start (none here)
    assert cfgmod.model_map() == {} and app.b_link_reset["state"] == "disabled"
    assert app.b_link_undo["state"] == "disabled"        # Undo takes back relinks only, not the reset
    app._link_models("flux2-vae.safetensors", "my_vae.safetensors")
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors"}
    assert "/vae/flux2-vae.safetensors  (your file: my_vae.safetensors)" in rows_text(app)
    assert app.rb_tabs["flux3"]["style"] == "Chip.Toolbutton" and app.inv.tab_status("flux3").state == "ready"
    g = {"1": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}}
    app.comfy.name_fixer(g)
    assert g["1"]["inputs"]["vae_name"] == "my_vae.safetensors"
    assert "flux2-vae.safetensors  →  my_vae.safetensors" in rows_text(app)
    assert any(r[0] == "links" for r in app._settings_rows()) and not any("extra_model_paths" in str(r) for r in app._settings_rows())
    app._link_models("flux2-vae.safetensors", "")         # "Unlink" in the list
    assert cfgmod.model_map() == {} and app.rb_tabs["flux3"]["style"] == "Missing.Chip.Toolbutton"
    app._settings_close()

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

    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES)})
    app._apply_refresh({"_detect": True, "_inv": None, "_inv_error": "x"})

    # a normal PhotoCraft/ComfyUI refresh still goes through the old path
    app._apply_refresh({"comfy": True})
    assert app.v_conn.get() == "ComfyUI connected" and app.lbl_dot.cget("style") == "ConnOk.TLabel"
    app._apply_refresh({"comfy": False})
    assert app.v_conn.get() == "ComfyUI not connected" and app.lbl_dot.cget("style") == "ConnBad.TLabel"
    test_start_state()
    test_empty_view()
    test_other_settings()
    test_page_layout_and_stop()
    print("ok")


if __name__ == "__main__":
    main()
