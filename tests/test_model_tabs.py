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
    assert [m.label for m in models.MODELS] == ["Qwen2.1", "Flux2Klein", "Flux3Klein", "MOSS Image", "Fibo 2.0 Edit"]

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
    assert app.v_workflow.get() == "qwen-image-21-edit.json" and app.v_res.get() == 1024 and app.v_turbo.get() is True
    assert app.rb_modes["edit"]["state"] == "normal" and app.rb_modes["upscale"]["state"] == "disabled"
    assert app.rb_modes["refine"]["state"] == "disabled"

    # the modes follow each other in the order text, edit, fill, expand, reference, remove, upscale, refine
    assert [k for k, _ in gui.MODE_LABELS] == ["txt2img", "edit", "inpaint", "outpaint", "reference", "remove", "upscale", "refine", "img2img"]

    # MOSS: text to image, Generative fill, Expand (a test); the DMD2 LoRA is its own LoRA, Lenovo and SLG are switches
    app.v_model.set("moss")
    app.v_mode.set("txt2img")
    app._on_model()
    assert app.v_mode.get() == "txt2img" and app.v_workflow.get() == "moss-image-t2i.json" and app.v_res.get() == 1280
    assert app.v_enhance.get() is False and "Qwen 3.5 9B" in app.tt_enhance.text      # which text model writes the prompt (starts off)
    assert app.cb_enhance["text"] == "LLM prompt enhancement (Qwen 3.5 9B)"
    assert app.v_turbo.get() is True and app.cb_turbo["text"].startswith("DMD2") and app.v_lora_str.get() == 1.0
    assert [k for k, rb in app.rb_modes.items() if rb["state"] == "normal"] == ["txt2img", "inpaint", "outpaint"]   # Generative fill works with the same inpaint workflow as Expand
    assert [c["text"] for c in app.stage_cbs] == ["Lenovo UltraReal LoRA", "Skip-layer guidance (SLG)", "Stage"]
    assert app.v_stage.get() and app.v_stage2.get()                                    # Lenovo on, SLG on
    r = app._request()
    assert r.stage_on is True and r.stages_off == [] and r.turbo is True
    assert r.stage_strengths == {"5": 1.0}                                              # the Lenovo LoRA has a strength slider
    app.v_sstr[0].set(0.6)
    assert app._request().stage_strengths == {"5": 0.6}
    app.v_sstr[0].set(1.0)
    assert r.sampler_override == {} and (app.v_steps.get(), app.v_cfg.get()) == (8, 1.5)   # the fields show the workflow's values
    app.v_turbo.set(False)
    app._on_workflow()
    assert (app.v_steps.get(), app.v_cfg.get()) == (25, 2.5)                              # without DMD2: the full recipe
    app.v_steps.set(30)
    assert app._request().sampler_override == {"steps": 30}
    app.v_turbo.set(True)
    app._on_workflow()
    assert app._request().mode == "txt2img" and app._layer_prefix() == "MOSS Image Text"
    app.v_mode.set("outpaint")
    app._on_mode()
    assert app.v_workflow.get() == "moss-image-inpaint.json" and app.v_res.get() == 1216 and app.v_match.get() == 0.5

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
    assert len(app.rb_tabs) == 5 and app.f_tabs is not None

    # Flux 3: upscale brings its workflow, 1.5 and the placeholder; edit takes the placeholder away again
    app.v_model.set("flux3")
    app.v_mode.set("upscale")
    app._on_model()
    assert app.v_workflow.get() == "flux3-klein-upscale.json" and app.v_scale.get() == "1.5"
    assert app.t_prompt.get("1.0", "end").strip() == models.FLUX3_DEFAULT            # the workflow's own prompt, to describe in front of
    assert app._hint_text == models.DESCRIBE_TIP
    app.v_mode.set("edit")
    app._on_mode()
    assert app._hint_text == ""
    assert app.v_workflow.get() == "flux3-klein-edit.json" and app.t_prompt.get("1.0", "end").strip() == ""
    app.t_prompt.insert("1.0", "make it night")
    app.v_mode.set("refine")
    app._on_mode()
    assert app.v_workflow.get() == "flux3-klein-upscale.json" and app.t_prompt.get("1.0", "end").strip() == "make it night"  # typed text stays

    # a model without the current mode: the first one it has
    app.v_model.set("flux2")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.v_mode.get() == "edit" and app.v_workflow.get() == "flux2-klein-edit.json"

    # Fibo: the text model picked under the prompt stays while the mode changes; the tab follows a loaded workflow
    app.v_model.set("fibo")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.v_workflow.get() == "fibo2-edit-plain.json" and app.v_enhance.get() is False
    assert list(app.cb_llm["values"]) == [lb for _, lb in models.FIBO.llm] and app.v_llm.get() == models.FIBO.llm[0][1]
    app.v_llm.set("Qwen 3.5 9B (bionic)")
    app._llm_picked()
    assert app.v_workflow.get() == "fibo2-edit-vgl-bionic-qwen35-9b.json" and app.v_enhance.get() is True
    app.v_mode.set("outpaint")
    app._on_mode()
    assert app.v_workflow.get() == "fibo2-edit-vgl-bionic-qwen35-9b.json" and app.v_model.get() == "fibo" and app.v_enhance.get() is True
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

    # text to image for Qwen, Expand for the Flux Kleins, Fibo Remove starts with a soft mask and 10 % feather
    for key, mode in (("qwen", "txt2img"), ("flux2", "outpaint"), ("flux3", "outpaint")):
        assert mode in models.BY_KEY[key].modes, (key, mode)
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
    assert float(app.v_scale.get()) == 1.5 and app._pchoice_key is None
    # Expand image: the prompt field turns orange with a hint
    app.v_mode.set("outpaint")
    app._on_model()
    assert app.t_prompt["highlightbackground"] == gui.ACCENT
    app.v_mode.set("edit")
    app._on_model()
    assert app.t_prompt["highlightbackground"] != gui.ACCENT
    assert models.BY_KEY["moss"].modes["txt2img"].settings["enhance"] is False   # MOSS: the prompt enhancer starts off
    assert gui.PROMPT_LINES == 5
    mm = models.BY_KEY
    assert mm["qwen"].modes["txt2img"].workflow == "qwen-image-21-t2i.json" and mm["qwen"].modes["txt2img"].settings["enhance"] is False
    assert mm["qwen"].modes["remove"].settings["feather_pct"] == 10.0 and mm["fibo"].modes["inpaint"].settings["feather_pct"] == 10.0
    assert mm["fibo"].modes["inpaint"].settings["layer_mask"] == "soft"
    assert mm["flux3"].modes["txt2img"].settings["enhance"] is False
    assert [p[0] for p in mm["flux2"].modes["refine"].prompts] == ["Default", "Neutral", "Studio portrait"]
    assert mm["flux3"].modes["refine"].prompts == () and mm["flux2"].modes["upscale"].prompts == ()   # Flux 3: the workflow's own prompt only
    # the prompt a refine starts with is the one the workflow sends by default
    import json as _j
    wf2 = _j.loads((t.ROOT / "workflows" / "flux2-klein-upscale.json").read_text(encoding="utf-8"))
    wf3 = _j.loads((t.ROOT / "workflows" / "flux3-klein-upscale.json").read_text(encoding="utf-8"))
    assert wf2["206"]["_meta"]["pc_default_prompt"] == models.FLUX2_DEFAULT == mm["flux2"].modes["refine"].prompt_hint
    assert wf3["24"]["_meta"]["pc_default_prompt"] == models.FLUX3_DEFAULT == mm["flux3"].modes["refine"].prompt_hint
    assert wf3["159"]["inputs"]["text"] == ["24", 0] and "158" not in wf3
    assert mm["flux2"].modes["refine"].prompt_tip == mm["flux3"].modes["upscale"].prompt_tip == "Describe the image for better results in front of the prompt."
    # Remove (a test) for Flux 2 and 3: the Qwen way, soft mask with 10 % feather
    for k in ("flux2", "flux3"):
        assert mm[k].modes["remove"].settings["feather_pct"] == 10.0 and mm[k].modes["remove"].settings["layer_mask"] == "soft"
    assert "inpaint" in mm["moss"].modes and mm["moss"].modes["inpaint"].workflow == "moss-image-inpaint.json"
    # every mode of every model has a tooltip of its own, and none of them names another model
    names = ("Qwen", "Fibo", "Flux", "MOSS")
    for m in models.MODELS:
        assert set(m.mode_tips) == set(m.modes), m.key
        for tip in m.mode_tips.values():
            others = [n for n in names if n.lower() not in (m.key, m.label.lower()) and n.lower() in tip.lower() and not m.label.lower().startswith(n.lower())]
            assert not others, (m.key, others)
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    q_tip = app.tt_modes["remove"].text
    app.v_model.set("fibo")
    app.v_mode.set("inpaint")
    app._on_model()
    assert app.tt_modes["remove"].text != q_tip and "Qwen" not in app.tt_modes["remove"].text
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
