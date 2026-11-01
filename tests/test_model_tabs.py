"""The model tabs: a tab enables only its model's modes, brings its workflow and starting settings, follows presets.

    python tests/test_model_tabs.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
from pccomfy import models  # noqa: E402


def main():
    # the registry: every workflow exists, every mode is a known one
    for m in models.MODELS:
        for w in m.workflows():
            assert (t.ROOT / "workflows" / w).exists(), (m.key, w)
        for mode in m.modes:
            assert mode in dict(gui.MODE_LABELS), (m.key, mode)
    assert [m.label for m in models.MODELS] == ["Flux 3 Klein Edit", "Flux 2 Klein Edit", "Qwen 2.1 Edit", "Fibo 2.0 Edit Turbo", "Krea 2 Turbo", "MOSS Image"]

    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names

    # Qwen: fill, remove, reference, expand, edit - no upscale
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.v_workflow.get() == "qwen-image-21-edit.json" and app.v_res.get() == 1024 and app.v_turbo.get() is False    # Qwen: Turbo off by default (27.10.)
    assert app.rb_modes["edit"]["state"] == "normal" and app.rb_modes["upscale"]["state"] == "normal"     # functions: never grey
    assert [k for k, rb in app.rb_tabs.items() if rb["state"] == "normal"] == ["qwen", "fibo"]          # models that can fill
    # a function the model cannot do picks a model that can (the fixed order: Flux 3 first); Qwen comes back for Fill
    app.v_mode.set("upscale"); app._on_mode()
    assert app.v_model.get() == "flux3" and app.v_workflow.get() == "flux3-klein-upscale.json"
    app.v_mode.set("inpaint"); app._on_mode()
    assert app.v_model.get() == "qwen"                                                                   # the last model of Fill
    app.v_mode.set("txt2img"); app._on_mode()
    assert app.v_model.get() == "qwen"                                                                   # Qwen can do it: stays
    app.v_mode.set("inpaint"); app._on_mode()

    # the modes follow each other in the order text, edit, fill, remove, expand, reference, upscale, refine
    assert [k for k, _ in gui.MODE_LABELS] == ["txt2img", "outpaint", "inpaint", "remove", "edit", "multi_edit", "upscale", "refine", "img2img"]

    # MOSS: text to image, Generative fill, Expand (a test); the DMD2 LoRA is its own LoRA, Lenovo and SLG are switches
    app.v_model.set("moss")
    app.v_mode.set("txt2img")
    app._on_model()
    assert app.v_mode.get() == "txt2img" and app.v_workflow.get() == "moss-image-t2i.json" and app.v_res.get() == 1280
    assert app.v_enhance.get() is False and "Qwen 3.5 9B" in app.tt_enhance.text      # which text model writes the prompt (starts off)
    assert app.cb_enhance["text"] == "LLM prompt enhancement" and "Qwen 3.5 9B" in app.tt_enhance.text   # name only in the tooltip
    assert app.v_turbo.get() is False and app.cb_turbo["text"].startswith("DMD2") and app.v_lora_str.get() == 1.0   # DMD2 starts off (user 29.10.)
    assert list(models.MOSS.modes) == ["txt2img"]                                                       # Fill off (not good enough), Expand parked 29.10.
    assert [c["text"] for c in app.stage_cbs] == ["UltraReal LoRA", "Skip-layer guidance (SLG)", "Stage"]
    assert app.v_stage.get() and not app.v_stage2.get()                                # Lenovo on, SLG off (user 29.10.)
    r = app._request()
    assert r.stage_on is True and r.stages_off == ["7"] and r.turbo is False
    assert r.stage_strengths == {"5": 1.0}                                              # the Lenovo LoRA has a strength slider
    app.v_sstr[0].set(0.6)
    assert app._request().stage_strengths == {"5": 0.6}
    app.v_sstr[0].set(1.0)
    assert r.sampler_override == {} and (app.v_steps.get(), app.v_cfg.get()) == (35, 3.0)  # without DMD2: the full recipe
    app.v_turbo.set(True)
    app._on_workflow()
    assert (app.v_steps.get(), app.v_cfg.get()) == (8, 1.5)                               # with DMD2: its own values
    app.v_turbo.set(False)
    app._on_workflow()
    app.v_steps.set(30)
    assert app._request().sampler_override == {"steps": 30}
    app.v_turbo.set(True)
    app._on_workflow()
    assert app._request().mode == "txt2img" and app._layer_prefix() == "MOSS Image Text"
    assert "outpaint" not in models.BY_KEY["moss"].modes          # MOSS Expand is parked since 29.10. (models.PARKED_EXPAND)

    # Flux 3: text to image and edit share the settings (base res 1536); Flux 2 edit starts at 1024
    app.v_model.set("flux3")
    app.v_mode.set("txt2img")
    app._on_model()
    assert app.v_workflow.get() == "flux3-klein-t2i.json" and app.v_res.get() == 1536
    app.v_mode.set("edit")
    app._on_mode()
    assert app.v_workflow.get() == "flux3-klein-edit.json" and app.v_res.get() == 1536
    app.v_model.set("flux2")
    app._on_model()
    assert app.v_res.get() == 1024 and app.v_match.get() == 0.0
    assert len(app.rb_tabs) == 6 and app.f_tabs is not None

    # Flux 3: upscale brings its workflow, 1.5 and the placeholder; edit takes the placeholder away again
    app.v_model.set("flux3")
    app.v_mode.set("upscale")
    app._on_model()
    assert app.v_workflow.get() == "flux3-klein-upscale.json" and app.v_scale.get() == "x 1.5"
    assert app.t_prompt.get("1.0", "end").strip() == models.FLUX3_DEFAULT            # the workflow's own prompt, to describe in front of
    assert app._hint_text == models.DESCRIBE_TIP
    app.v_mode.set("edit")
    app._on_mode()
    assert app._hint_text == models.EDIT_TIP + " " + models.EDIT_AGAIN    # the tip under the prompt in Edit Canvas (Flux 3)
    assert app.v_workflow.get() == "flux3-klein-edit.json" and app.t_prompt.get("1.0", "end").strip() == ""
    app.t_prompt.insert("1.0", "make it night")
    app.v_mode.set("upscale")
    app._on_mode()
    assert app.v_workflow.get() == "flux3-klein-upscale.json" and app.t_prompt.get("1.0", "end").strip() == "make it night"  # typed text stays
    assert "refine" in models.BY_KEY["flux3"].modes                                      # Flux 3 Refine (after Pixaroma, 1.11.)

    # a model without the current mode: the first one it has
    app.v_model.set("flux2")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.v_mode.get() == "txt2img" and app.v_workflow.get() == "flux2-klein-t2i.json"      # Flux 2 starts with text to image

    # Fibo: one workflow with the LLM checkbox; its state stays while the mode changes; the tab follows a loaded workflow
    app.v_model.set("fibo")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.v_workflow.get() == "fibo2-edit.json" and app.v_enhance.get() is False
    assert app.cb_enhance["text"] == "LLM prompt enhancement" and "Qwen 3.5 9B" in app.tt_enhance.text   # name only in the tooltip
    app.v_enhance.set(True)
    app.v_mode.set("edit")
    app._on_mode()
    assert app.v_enhance.get() is True and app._request().enhance is True                # the choice survives a mode change
    app.v_mode.set("outpaint")
    app._on_mode()
    assert app.v_workflow.get() == "fibo2-edit.json" and app.v_model.get() == "fibo"
    assert app._request().enhance is False                                               # Expand: no prompt writer
    app.v_mode.set("edit")
    app._on_mode()
    assert app._request().enhance is True
    app.v_enhance.set(False)
    app._apply_settings({"workflow": "qwen-image-21-edit.json", "mode": "inpaint"})
    assert app.v_model.get() == "qwen"

    # extra LoRAs: rows, search order (the model's folder first), request, state
    app.all_loras = ["flux 3\\b.safetensors", "qwen\\style_a.safetensors", "qwen\\Style_B.safetensors", "misc\\c.safetensors"]
    app.v_model.set("qwen")
    assert app._lora_choices()[:2] == ["qwen\\style_a.safetensors", "qwen\\Style_B.safetensors"]
    assert app._lora_choices("style b") == ["qwen\\Style_B.safetensors"]
    app._add_lora_row("qwen\\style_a.safetensors", 0.6)
    app._add_lora_row("", 1.0)                       # an empty row is not a LoRA
    row0 = app.lora_rows[0]
    row0["name"].set("style b")
    app._lora_show(row0, "style b")                  # typing opens the list, narrowed to what was typed
    assert row0["box"] is not None
    app._lora_show(row0, "zzz-no-such")              # nothing matches: the list goes away
    assert row0["box"] is None
    app._lora_toggle(row0)                            # the arrow lists everything
    assert row0["box"] is not None
    app._lora_hide(row0)
    row0["name"].set("qwen\\style_a.safetensors")
    assert app._request().loras == [("qwen\\style_a.safetensors", 0.6)]
    assert app._collect()["loras"] == [["qwen\\style_a.safetensors", 0.6]]
    for _ in range(6):
        app._add_lora_row("misc\\c.safetensors")
    assert len(app.lora_rows) == app.LORA_MAX and app.b_addlora["state"] == "disabled"
    app._set_loras([["x", 0.3]])
    assert len(app.lora_rows) == 1 and app._loras() == [["x", 0.3]] and app.b_addlora["state"] == "normal"
    app._apply_settings({"loras": []})
    assert app._loras() == []
    app._set_loras([["qwen\\style_a.safetensors", 0.6]])

    # text to image for Qwen, Expand for Flux 2 and Flux 3, not for Krea 2 (off 29.10.); Fibo Remove starts with a soft mask and 10 % feather
    for key, mode in (("qwen", "txt2img"), ("flux2", "outpaint"), ("flux3", "outpaint")):
        assert mode in models.BY_KEY[key].modes, (key, mode)
    assert "outpaint" not in models.BY_KEY["krea2"].modes
    app.v_model.set("fibo")
    app.v_mode.set("remove")
    app._on_model()
    assert app.v_lmask.get() == gui.LAYER_MASKS["soft"] and app.v_feather.get() == 10.0
    assert gui.LAYER_MASKS["soft"] == "soft"
    # Flux 2 refine: ready-made prompts as radio buttons that fill the field; upscale starts at 1.5
    app.v_model.set("flux2")
    app.v_mode.set("refine")
    app._on_model()
    assert app._pchoice_key == ("flux2", "refine")
    app._insert_prompt(models.RELIGHT_NEUTRAL)
    assert app._prompt_text().startswith("A crystal-clear, high-fidelity photograph")
    app.v_mode.set("upscale")
    app._on_model()
    assert app._scale() == 1.5 and app.v_scale.get() == "x 1.5" and app._pchoice_key is None
    # Expand image: the prompt field turns orange with a hint
    app.v_mode.set("outpaint")
    app._on_model()
    assert app.t_prompt["highlightbackground"] == gui.ACCENT
    app.v_mode.set("edit")
    app._on_model()
    assert app._hint_text.startswith(models.EDIT_TIP)   # Edit Canvas: the tip under the prompt, also orange
    app.v_mode.set("txt2img")
    app._on_model()
    assert app._hint_text == models.T2I_TIP             # Text to image: says that a new image is added, also orange
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app._hint_text == models.FILL_TIP + " " + models.QWEN_SMALL and app.t_prompt["highlightbackground"] == gui.ACCENT   # Fill: the tip under the prompt (28.10.)
    app.v_model.set("flux2")
    app.v_mode.set("txt2img")
    app._on_model()
    assert models.BY_KEY["moss"].modes["txt2img"].settings["enhance"] is False   # MOSS: the prompt enhancer starts off
    assert gui.PROMPT_LINES == 5
    mm = models.BY_KEY
    assert mm["qwen"].modes["txt2img"].workflow == "qwen-image-21-t2i.json" and mm["qwen"].modes["txt2img"].settings["enhance"] is False and mm["qwen"].modes["txt2img"].settings["turbo"] is False
    assert mm["qwen"].modes["remove"].settings["feather_pct"] == 10.0 and mm["fibo"].modes["inpaint"].settings["feather_pct"] == 10.0
    assert mm["fibo"].modes["inpaint"].settings["layer_mask"] == "soft" == mm["qwen"].modes["inpaint"].settings["layer_mask"]   # soft edge outside the selection (28.10.)
    assert mm["flux3"].modes["txt2img"].settings["enhance"] is False
    # "auto" left the menu (28.10.): no mode uses it, and Expand keeps exactly what "auto" gave it before
    from pccomfy.bridge import effective_layer_mask, is_editor
    from pccomfy import workflows as _wfs
    for m in models.MODELS:
        for key, spec in m.modes.items():
            assert spec.settings.get("layer_mask") != "auto", (m.key, key)
        if "outpaint" in m.modes:
            spec = m.modes["outpaint"]
            ed = is_editor(_wfs.resolve(str(t.ROOT / "workflows" / spec.workflow)))
            assert spec.settings["layer_mask"] == effective_layer_mask("auto", "outpaint", ed, True), m.key
    assert mm["fibo"].modes["inpaint"].prompt_tip == models.FILL_TIP   # the user's wording
    assert mm["qwen"].modes["inpaint"].prompt_tip == models.FILL_TIP + " Small selections don't work well with Qwen."   # user 30.10.
    assert models.FILL_TIP == "Draw a selection and prompt e.g. “a red flower”. Hide layers from previous results before running again."
    assert [p[0] for p in mm["flux2"].modes["refine"].prompts] == ["Default", "Neutral", "Studio portrait"]
    assert mm["flux3"].modes["upscale"].prompts == () and mm["flux2"].modes["upscale"].prompts == ()   # Flux 3: the workflow's own prompt only
    # the prompt a refine starts with is the one the workflow sends by default
    import json as _j
    wf2 = _j.loads((t.ROOT / "workflows" / "flux2-klein-upscale.json").read_text(encoding="utf-8"))
    wf3 = _j.loads((t.ROOT / "workflows" / "flux3-klein-upscale.json").read_text(encoding="utf-8"))
    assert wf2["206"]["_meta"]["pc_default_prompt"] == models.FLUX2_DEFAULT == mm["flux2"].modes["refine"].prompt_hint
    assert wf3["24"]["_meta"]["pc_default_prompt"] == models.FLUX3_DEFAULT == mm["flux3"].modes["upscale"].prompt_hint
    assert wf3["159"]["inputs"]["text"] == ["24", 0] and "158" not in wf3
    assert mm["flux2"].modes["refine"].prompt_tip == mm["flux3"].modes["upscale"].prompt_tip == models.DESCRIBE_TIP
    assert models.DESCRIBE_TIP == "Add a short description of your image in front of this text."   # user 28.10.
    # Remove (a test) for Flux 2 and 3: the Qwen way, soft mask with 10 % feather
    for k in ("flux2", "flux3"):
        assert mm[k].modes["remove"].settings["feather_pct"] == 10.0 and mm[k].modes["remove"].settings["layer_mask"] == "soft"
    assert "inpaint" not in mm["moss"].modes
    # one general tooltip per function, the same on every tab, naming no model (user 28.10.); model notes go under the prompt
    names = ("Qwen", "Fibo", "Flux", "MOSS", "Krea", "SeedVR")
    assert set(models.FUNCTION_TIPS) >= {k for m in models.MODELS for k in m.modes}
    assert not [n for n in names for tip in models.FUNCTION_TIPS.values() if n.lower() in tip.lower()]
    tips = {}
    for key in ("qwen", "fibo", "flux2"):
        app.v_model.set(key)
        app.v_mode.set("inpaint" if key != "flux2" else "remove")
        app._on_model()
        tips[key] = app.tt_modes["remove"].text
    assert tips["qwen"] == tips["fibo"] == tips["flux2"] == models.function_tip("remove", models.FUNCTION_TIPS["remove"])
    assert mm["flux2"].modes["remove"].prompt_tip.endswith(models.REMOVE_AGAIN)
    assert mm["fibo"].modes["refine"].prompt_tip == models.DESCRIBE_TIP + " Change the prompt for other edits."
    # every function's tooltip starts with the ranking (user 28.10.); a function without one says so
    assert models.ranking_text("inpaint") == "Ranking: 1. Fibo, 2. Qwen."
    assert models.ranking_text("remove") == "Ranking: 1. Fibo, 2. Qwen (not ranked: Flux 3, Flux 2)."
    assert models.ranking_text("outpaint") == "Ranking: 1. Flux 2, 2. Flux 3, 3. Qwen, 4. Fibo."      # Krea 2 / MOSS Expand off 29.10.
    assert models.ranking_text("edit").startswith("Ranking: 1. Flux 3, 2. Qwen, 3. Flux 2, 4. Fibo") and models.ranking_text("img2img") == ""   # all functions are ranked since 1.11.
    assert app.tt_modes["remove"].text.startswith("Ranking: 1. Fibo, 2. Qwen")
    assert all(k in models.SHORT for k in models.BY_KEY) and all(k in models.BY_KEY for r in models.RANKING.values() for k in r)
    # Fibo Refine starts with Sharpen 10 % (user 30.10.), Fibo Text to image with 20 % (user 28.10.); the box shows the percent
    for mode, want in (("refine", 0.1), ("txt2img", 0.2)):
        app.v_sharpen.set(0.0)
        app.v_model.set("fibo")
        app.v_mode.set(mode)
        app._on_model()
        assert app.v_sharpen.get() == want and app.lbl_sharpen.cget("text") == f"{round(want * 100)} %", (mode, app.v_sharpen.get())
        app.v_sharpen.set(0.0)
        app.reset_settings()
        assert app.v_sharpen.get() == want and app.lbl_sharpen.cget("text") == f"{round(want * 100)} %", (mode, "reset")
    # Fibo: text to image has its own workflow (no image inputs), Refine runs as a whole-image edit with a ready prompt
    assert mm["fibo"].modes["txt2img"].workflow == "fibo2-t2i.json" and mm["fibo"].modes["refine"].run_as == "edit"
    assert mm["fibo"].modes["refine"].prompt_hint == models.FLUX2_DEFAULT      # the Flux 2 Refine default (user 28.10.)
    assert models.FIBO_REFINE in models.STOCK_PROMPTS     # the old Fibo Refine text in a saved field is still replaced
    app.v_model.set("fibo")
    app.v_mode.set("refine")
    app._on_model()
    assert app.v_workflow.get() == "fibo2-edit.json" and app._request().mode == "edit"
    assert app._prompt_text() == models.FLUX2_DEFAULT and app.v_mode.get() == "refine" and app._layer_prefix().endswith("Refine")
    app.v_mode.set("txt2img")
    app._on_mode()
    assert app.v_workflow.get() == "fibo2-t2i.json" and app._request().mode == "txt2img" and app._prompt_text() == ""
    app.v_mode.set("edit")
    app._on_mode()
    assert app.v_workflow.get() == "fibo2-edit.json"
    # Remove Selection for Flux: the field is free for an optional name of the object; it travels as remove_target
    for k in ("flux2", "flux3"):
        app.v_model.set(k)
        app.v_mode.set("remove")
        app._on_model()
        assert str(app.t_prompt.cget("state")) == "normal" and app._hint_text.startswith(models.REMOVE_NAME_TIP), k
        assert app._request().remove_target == ""
        app.t_prompt.insert("1.0", "the dog")
        assert app._request().remove_target == "the dog" and app._request().mode == "remove"
        app.t_prompt.delete("1.0", "end")
        app.v_mode.set("edit")
        app._on_mode()
        assert app._request().remove_target == ""
    app.v_model.set("qwen")
    app.v_mode.set("remove")
    app._on_model()
    assert app.t_prompt.get("1.0", "end").strip() == ""
    # the copy button for the enhanced prompt
    assert app._last_vgl == ""
    app.root.clipboard_clear = lambda: None
    got = []
    app.root.clipboard_append = lambda x: got.append(x)
    app._last_vgl = "a long enhanced prompt"
    app._copy_enhanced()
    assert got == ["a long enhanced prompt"]

    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    app._set_loras([["qwen\\style_a.safetensors", 0.6]])
    # saved with the state
    app._save_state(app._request())
    import json
    assert json.loads((Path(t.TMP) / "state.json").read_text(encoding="utf-8"))["model"] == "qwen"
    assert json.loads((Path(t.TMP) / "state.json").read_text(encoding="utf-8"))["loras"] == [["qwen\\style_a.safetensors", 0.6]]
    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (model tabs)")


if __name__ == "__main__":
    main()
