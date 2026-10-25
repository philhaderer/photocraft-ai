"""Window round 5: what is hidden where (Expand, Edit, LoRA box), Mix source reset, sampler / scheduler, layer names.

    python tests/test_round5.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
from pccomfy import models, workflows  # noqa: E402


def rec(widget, name):
    """Record the calls of a geometry method of a stub widget."""
    calls = []
    setattr(widget, name, lambda *a, **k: calls.append((name, k)))
    return calls


def main():
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names

    def pick(key, mode):
        app.v_model.set(key)
        app.v_mode.set(mode)
        app._on_model()

    # Layer mask: hidden for Text to image, Edit whole image (every model) and Expand image; shown for Fill
    lm = rec(app.f_lm, "pack_forget")
    for key in ("qwen", "flux2", "flux3", "fibo"):
        lm.clear()
        pick(key, "edit")
        assert lm, (key, "layer mask must be hidden in Edit whole image")
    for key in ("qwen", "flux2", "flux3", "moss", "fibo"):
        lm.clear()
        pick(key, "outpaint")
        assert lm, (key, "layer mask must be hidden in Expand image")
    lm.clear()
    pick("qwen", "inpaint")
    assert not lm, "layer mask stays in Generative fill"
    lm.clear()
    pick("fibo", "refine")           # Fibo Refine runs as a whole-image edit
    assert lm

    # Expand image: Sharpen, Match colours, LLM enhancement and the prompt writer are gone
    sharp = [rec(w, "grid_remove") for w in app._sharp_widgets]
    match = [rec(w, "grid_remove") for w in app._match_widgets]
    app.f_enh.winfo_manager = lambda: "pack"       # the stub reports no geometry manager: say it is shown
    enh = rec(app.f_enh, "pack_forget")
    pick("fibo", "outpaint")
    assert all(sharp) and all(match) and enh
    assert app._request().sharpen == 0.0 and app._request().enhance is False
    app.v_sharpen.set(0.4)
    assert app._request().sharpen == 0.0                       # not applied in Expand ...
    app._save_state(app._request())
    assert json.loads((Path(t.TMP) / "state.json").read_text(encoding="utf-8"))["sharpen"] == 0.4   # ... and not forgotten
    pick("fibo", "edit")
    assert app._request().sharpen == 0.4
    # Expand sends no prompt enhancement even when the checkbox is on
    app.v_enhance.set(True)
    app.v_mode.set("outpaint")
    app._on_mode()
    assert app.v_workflow.get() == "fibo2-edit.json" and app._request().enhance is False
    app.v_enhance.set(False)
    # Match colours only in Fill and Reference
    for mode, shown in (("inpaint", True), ("reference", True), ("outpaint", False), ("edit", False)):
        grid = [rec(w, "grid") for w in app._match_widgets]
        gone = [rec(w, "grid_remove") for w in app._match_widgets]
        pick("fibo", mode)
        assert (all(grid) and not any(gone)) if shown else (all(gone) and not any(grid)), mode

    # The LoRA box: shown where the workflow has a LoRA of its own, hidden (not greyed out) where not
    shown, hidden = rec(app.cb_turbo, "grid"), rec(app.cb_turbo, "grid_remove")
    pick("qwen", "edit")
    assert shown and not hidden
    shown.clear(); hidden.clear()
    pick("fibo", "edit")
    assert hidden and not shown
    pick("qwen", "edit")
    pick("fibo", "txt2img")

    # Mix source image/new image goes back to 100 % when a function is chosen
    pick("flux2", "refine")
    app.v_detail.set(0.4)
    pick("flux2", "upscale")
    assert app.v_detail.get() == 1.0
    app.v_detail.set(0.4)
    app.v_mode.set("refine")
    app._on_mode()
    assert app.v_detail.get() == 1.0

    # Layer names: the model's "Edit" is not doubled
    pick("fibo", "edit")
    assert app._layer_prefix() == "Fibo 2.0 Edit"
    pick("flux3", "edit")
    assert app._layer_prefix() == "Flux 3 Klein Edit"
    pick("flux3", "remove")
    assert app._layer_prefix() == "Flux 3 Klein Edit Remove Selection"
    pick("qwen", "remove")
    assert app._layer_prefix() == "Qwen 2.1 Edit Remove Selection" and dict(gui.MODE_LABELS)["remove"] == "Remove Selection"

    # Sampler / scheduler: usable (readonly) where the workflow has them, a change is sent as an override
    pick("qwen", "edit")
    assert app.cb_sampler["state"] == "readonly" and app.cb_sched["state"] == "readonly", (app.cb_sampler["state"], app.cb_sched["state"])
    assert "sampler" not in app._request().sampler_override
    app.v_sampler.set("dpmpp_2m")
    app.v_scheduler.set("karras")
    assert app._request().sampler_override == {"sampler": "dpmpp_2m", "scheduler": "karras"}
    pick("flux2", "edit")                                   # SamplerCustomAdvanced: the sampler only
    assert app.cb_sampler["state"] == "readonly" and app.cb_sched["state"] == "disabled"

    # the workflow side: KSampler and KSamplerSelect
    tpl = workflows.load_template(t.ROOT / "workflows" / "qwen-image-21-edit.json")
    g = workflows.set_sampler(tpl, sampler="dpmpp_2m", scheduler="karras", steps=12)
    ks = g["10"]["inputs"]
    assert (ks["sampler_name"], ks["scheduler"], ks["steps"]) == ("dpmpp_2m", "karras", 12)
    assert tpl["10"]["inputs"]["sampler_name"] == "euler"   # the template itself is untouched
    f2 = workflows.load_template(t.ROOT / "workflows" / "flux2-klein-edit.json")
    assert workflows.sampler_values(f2) == {"sampler": "euler"}
    assert workflows.set_sampler(f2, sampler="dpmpp_2m", scheduler="karras")["198"]["inputs"]["sampler_name"] == "dpmpp_2m"

    # Krea 2 Turbo: Text to image (prompt enhancer switchable) and Expand (mask workflow); no LoRA box
    from pccomfy import bridge
    assert [k for k, rb in models.BY_KEY["krea2"].modes.items()] == ["txt2img", "outpaint"]
    k2 = workflows.load_template(t.ROOT / "workflows" / "krea2-turbo-t2i.json")
    ki = workflows.load_template(t.ROOT / "workflows" / "krea2-turbo-inpaint.json")
    for g in (k2, ki):
        assert all(str(v[0]) in g for n in g.values() for v in n["inputs"].values() if isinstance(v, list))
    assert workflows.writer_name(k2) == "Qwen 3 VL 4B" and not workflows.lora_switches(k2) and bridge.mask_is_used(ki) and not bridge.mask_is_used(k2)
    on, out = workflows.apply_template(k2, workflows.GenParams(prompt="a fox", seed=3, width=1024, height=768, batch=2), None, None)
    assert on[out]["class_type"] == "PreviewImage" and next(n for n in on.values() if n["class_type"] == "TextGenerate")["inputs"]["prompt"] == "a fox"
    assert next(n for n in on.values() if n["class_type"] == "EmptyLatentImage")["inputs"]["width"] == 1024
    off, _ = workflows.apply_template(workflows.bypass_prompt_writer(k2, "a fox"), workflows.GenParams(prompt="a fox", seed=3, width=1024, height=768), None, None)
    assert not any(n["class_type"] == "TextGenerate" for n in off.values())
    assert next(n for n in off.values() if n["class_type"] == "CLIPTextEncode")["inputs"]["text"] == "a fox"
    pick("krea2", "txt2img")
    assert app.v_workflow.get() == "krea2-turbo-t2i.json" and app.v_res.get() == 1024 and app.v_enhance.get() is False
    pick("krea2", "outpaint")
    assert app.v_workflow.get() == "krea2-turbo-inpaint.json"
    # the names: Fill Selection, no Bionic anywhere, one Fibo workflow with the LLM checkbox
    assert dict(gui.MODE_LABELS)["inpaint"] == "Fill Selection" and gui.SHORT_MODES["inpaint"] == "Fill Selection"
    assert sorted(p.name for p in (t.ROOT / "workflows").glob("fibo2*")) == ["fibo2-edit.json", "fibo2-t2i.json"]
    assert not any("bionic" in p.read_text(encoding="utf-8").lower() for p in (t.ROOT / "workflows").glob("*.json"))
    # the LoRA / stage box sits directly under the negative prompt, a light line above Advanced
    packs = rec(app.f_opts, "pack")
    app.f_opts.winfo_manager = lambda: ""
    app._update_options_box(True, [])
    assert packs and packs[0][1].get("after") is app.f_neg, packs
    assert app.sep_adv is not None

    # Restore LoRA (AusBoss loader): the name is matched against the server's list; a missing file is an error, never a silent skip
    f3 = workflows.load_template(t.ROOT / "workflows" / "flux3-klein-upscale.json")
    assert f3["9"]["inputs"]["on_missing"] == "error"
    g3, miss = workflows.fix_lora_names(f3, ["Flux 3\\flux-3-image-klein-restore.safetensors"])
    assert not miss and json.loads(g3["9"]["inputs"]["loras"])[0]["name"] == "Flux 3\\flux-3-image-klein-restore.safetensors"
    g3, miss = workflows.fix_lora_names(f3, ["Flux 3/Flux-3-Image-Klein-Restore.safetensors"])      # other separator / case: the listed name is used
    assert not miss and json.loads(g3["9"]["inputs"]["loras"])[0]["name"] == "Flux 3/Flux-3-Image-Klein-Restore.safetensors"
    _, miss = workflows.fix_lora_names(f3, ["Flux 2\\ultra_real_v4.safetensors"])
    assert miss == ["Flux 3\\flux-3-image-klein-restore.safetensors"]
    off, miss = workflows.fix_lora_names(workflows.bypass_lora(f3), [])                          # switched off: nothing to find
    assert not miss
    # Remove Selection: the text box is usable on every model that has the function
    for key in ("qwen", "flux2", "flux3", "fibo"):
        assert models.BY_KEY[key].modes["remove"].remove_text, key
    assert [k for k, _ in gui.MODE_LABELS][:6] == ["txt2img", "edit", "inpaint", "remove", "outpaint", "reference"]

    # Flux 3: 15 steps in every workflow (the SeedVR2 pre-stage keeps its one step); Upscale shows "x 1.5"; a line above "Prompt"
    for wf in ("flux3-klein-edit.json", "flux3-klein-t2i.json", "flux3-klein-upscale.json"):
        assert workflows.sampler_values(workflows.load_template(t.ROOT / "workflows" / wf))["steps"] == 15, wf
    assert app.sep_prompt is not None and gui.scale_text(1.5) == "x 1.5" and gui.scale_text("2.0") == "x 2"

    # Remove Selection with the name of the object (Flux Klein): the instruction names it; runs.jsonl says what was sent
    import tempfile
    import test_reference_mode as T
    from pccomfy import bridge
    from pccomfy.bridge import Request
    for target, expect in (("", "Erase everything inside the red rectangle"), ("the dog", "Remove the dog that is inside the red rectangle")):
        pc, _, b = T.make(tempfile.mkdtemp(), layers=2)
        b.comfy = T.FakeComfy()
        req = Request(mode="remove", workflow=str(t.ROOT / "workflows" / "flux3-klein-edit.json"), enhance=False, remove_target=target)
        req.params = workflows.GenParams(prompt=target, seed=7)
        b.run(req)
        sent = next(n["inputs"]["text"] for n in b.comfy.graphs[0].values() if n["class_type"] == "CLIPTextEncode")
        assert sent.startswith(expect), sent
        log = [json.loads(x) for x in (b.exchange / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
        assert log[-1]["mode"] == "remove" and log[-1]["workflow"] == "flux3-klein-edit.json" and log[-1]["prompt"] == sent
    from PIL import Image
    assert bridge.remove_prompt(Image.new("L", (10, 10), 255), 1, "a car").startswith("Delete a car")

    shutil.rmtree(t.TMP, ignore_errors=True)
    print("ALL OK (round 5)")


if __name__ == "__main__":
    main()
