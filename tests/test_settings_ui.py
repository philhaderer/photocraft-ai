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
from pccomfy import inventory, manifest, models  # noqa: E402


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


def main():
    app = make_app()

    # the hooks: SettingsMixin first, a gear button, a tooltip object per tab
    assert gui.App.__mro__[1].__name__ == "SettingsMixin"
    assert app.b_gear is not None and set(app.tt_tabs) == {m.key for m in models.MODELS}
    assert app.inv is None
    app.v_model.set("flux3")
    app.v_mode.set("edit")
    app._on_model()
    assert app.v_model.get() == "flux3" and app._last_model == "flux3"
    assert [k for k in models.FLUX3.modes if app.rb_modes[k]["state"] == "normal"] == list(models.FLUX3.modes)    # nothing read yet: nothing greyed

    # a full install: nothing is grey, no extra tooltip text
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(td.full_lists(), NODES), "_yaml": [], "_disk": {}})
    assert all(rb["style"] == "Tab.Toolbutton" for rb in app.rb_tabs.values())
    assert app.tt_tabs["flux3"].text == models.FLUX3.tip
    assert app.comfy.name_fixer is not None
    assert app._preflight() == []

    # SeedVR2 missing: Flux 3 stays a normal tab, only Upscale is greyed and says why
    inv = inventory.Inventory(lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), NODES)
    app._apply_refresh({"_detect": True, "_inv": inv, "_yaml": [], "_disk": {}})
    assert app.rb_tabs["flux3"]["style"] == "Tab.Toolbutton"
    assert app.rb_modes["upscale"]["state"] == "disabled" and app.rb_modes["edit"]["state"] == "normal"
    assert "Missing for Upscale (new file): seedvr2_3b_int8_convrot.safetensors. Set in settings" in app.tt_modes["upscale"].text
    assert app.tt_modes["upscale"].text.startswith(models.FLUX3.mode_tips["upscale"])
    assert "Missing for Upscale" in app.tt_tabs["flux3"].text and app.tt_tabs["flux3"].text.startswith(models.FLUX3.tip)
    app._update_mode_radios()          # called again (a tab switch does that): the tooltip does not grow
    assert app.tt_modes["upscale"].text.count("Missing for") == 1

    # Krea 2's VAE missing: the tab is grey, its tooltip says what; the Flux 3 tab is still the selected one
    inv = inventory.Inventory(lists_without(vae="qwen_image_vae.safetensors"), NODES)
    app._apply_refresh({"_detect": True, "_inv": inv, "_yaml": [], "_disk": {}})
    assert app.rb_tabs["krea2"]["style"] == "Missing.Tab.Toolbutton" and app.rb_tabs["flux3"]["style"] == "Tab.Toolbutton"
    assert app.tt_tabs["krea2"].text == models.KREA2.tip + "\n\nMissing: qwen_image_vae.safetensors. Set in settings (gear)."
    assert app.rb_modes["upscale"]["state"] == "normal"            # the SeedVR2 problem is gone with the new reading

    # a click on the grey tab opens the settings instead of switching
    app.v_model.set("krea2")
    app._on_model()
    assert app.v_model.get() == "flux3" and app._last_model == "flux3"
    assert app._settings_win is not None and app._settings_focus == "krea2"
    text = "".join(p for p, _tags in app.t_settings.parts)
    assert "Installed models" in text and "Credits" in text and "\u25C0" in text
    assert "\u2717 qwen_image_vae.safetensors" in text and "ComfyUI\\models\\vae" in text
    assert app.v_set_conn.get() == "ComfyUI \u25CF"
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
    assert called == ["krea2"] and app.rb_tabs["krea2"]["style"] == "Tab.Toolbutton" and app.inv.tab_status("krea2").state == "ready"

    # a workflow of your own (no tab) and an unreachable ComfyUI never stop a run
    app.v_model.set("")
    app.generate()
    assert called == ["krea2", ""]
    app._apply_refresh({"_detect": True, "_inv": None, "_inv_error": "No connection to ComfyUI", "_yaml": [], "_disk": {}})
    assert app.inv is None and app.comfy.name_fixer is None and all(rb["style"] == "Tab.Toolbutton" for rb in app.rb_tabs.values())
    app.v_model.set("krea2")
    app.generate()
    assert called == ["krea2", "", "krea2"]
    app.open_settings()
    text = "".join(p for p, _tags in app.t_settings.parts)
    assert "ComfyUI could not be read." in text and "No connection to ComfyUI" in text and app.v_set_conn.get() == "ComfyUI \u25CB"
    app._settings_close()

    # the overlay text: downloads are links, a missing node names its pack, the credits are links
    inv = inventory.Inventory(lists_without(unet="seedvr2_3b_int8_convrot.safetensors"), {"SeedVR2Preprocess"})
    app._apply_refresh({"_detect": True, "_inv": inv, "_yaml": [], "_disk": {"seedvr2_3b_int8_convrot.safetensors": ["D:/models/diffusion_models/seedvr2_3b_int8_convrot.safetensors"]}})
    seg = app._settings_segments()
    links = [u for _t, style, u in seg if style == "link"]
    assert "https://huggingface.co/Comfy-Org/SeedVR2" in links and "https://github.com/ausboss/ComfyUI-AusBoss" in links
    assert all(u.startswith("https://") for u in links) and len(links) >= len(manifest.CONTRIBUTORS)
    joined = "".join(s for s, _st, _u in seg)
    assert "node AUSBOSS_NODES_TiledUpscale" in joined and "found on disk: D:/models/diffusion_models/seedvr2" in joined
    assert "Peszemeszek" in joined and "optional" in joined and "(as " not in joined

    # link a file of another name: the tab turns ready at once and graphs get the real name
    lists = td.full_lists()
    lists["vae"].remove("flux2-vae.safetensors")
    lists["vae"].append("my_vae.safetensors")
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists, NODES), "_yaml": [], "_disk": {}})
    assert app.rb_tabs["flux3"]["style"] == "Missing.Tab.Toolbutton" and app.rb_tabs["fibo"]["style"] == "Missing.Tab.Toolbutton"
    app.open_settings()
    exp, avail = app._link_choices()
    assert "flux2-vae.safetensors" in exp and "my_vae.safetensors" in avail["vae"]
    app.v_link_exp.set("flux2-vae.safetensors")
    app._link_expected_picked()
    assert "my_vae.safetensors" in app.cb_link_act["values"] and "flux3-image-klein-int8-convrot.safetensors" not in app.cb_link_act["values"]
    app.v_link_act.set("my_vae.safetensors")
    app._link_models()
    assert cfgmod.model_map() == {"flux2-vae.safetensors": "my_vae.safetensors"}
    assert app.rb_tabs["flux3"]["style"] == "Tab.Toolbutton" and app.inv.tab_status("flux3").state == "ready"
    g = {"1": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}}}
    app.comfy.name_fixer(g)
    assert g["1"]["inputs"]["vae_name"] == "my_vae.safetensors"
    assert "flux2-vae.safetensors  \u2192  my_vae.safetensors" in "".join(s for s, _st, _u in app._settings_segments())
    app.v_link_exp.set("flux2-vae.safetensors")
    app._unlink_model()
    assert cfgmod.model_map() == {} and app.rb_tabs["flux3"]["style"] == "Missing.Tab.Toolbutton"
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

    # a normal PhotoCraft/ComfyUI refresh still goes through the old path
    app._apply_refresh({"pc": "PhotoCraft \u25CF", "comfy": "ComfyUI \u25CF"})
    assert app.v_conn.get() == "PhotoCraft \u25CF   ComfyUI \u25CF"
    print("ok")


if __name__ == "__main__":
    main()
