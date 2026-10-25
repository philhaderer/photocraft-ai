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
    # the prompt writer drop-down is not offered in Expand
    app.v_llm.set("Qwen 3.5 9B (bionic)")
    app._llm_picked()
    assert app.v_workflow.get() == "fibo2-edit-vgl-bionic-qwen35-9b.json"
    app.v_mode.set("outpaint")
    app._on_mode()
    assert app.v_workflow.get() == "fibo2-edit-plain.json" and app.v_enhance.get() is False
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
    assert app._layer_prefix() == "Flux3Klein Edit"
    pick("flux3", "remove")
    assert app._layer_prefix() == "Flux3Klein Edit Remove Selection"
    pick("qwen", "remove")
    assert app._layer_prefix() == "Qwen2.1 Remove Selection" and dict(gui.MODE_LABELS)["remove"] == "Remove Selection"

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
