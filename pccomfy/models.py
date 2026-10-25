"""The models the window offers as tabs, and what each of them can do.

A tab is a model; below it only the modes that work well with it are enabled. Each mode names the workflow that runs it and
the settings it starts with (the same keys a preset saves). What a model can do comes from live tests; see the project
notes ("plugin-erfahrungen"): add a mode here once it has been tried.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PLACEHOLDER = "<DESCRIBE THE IMAGE>"


@dataclass(frozen=True)
class Mode:
    workflow: str
    settings: dict = field(default_factory=dict)
    prompt_hint: str = ""           # what an empty prompt field starts with in this mode


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    tip: str
    modes: dict                     # mode key -> Mode (a mode that is not here is greyed out)
    alt_workflows: tuple = ()       # more workflows of this model
    llm: tuple = ()                 # (workflow, label) of the text models that can write the prompt (a drop-down under the prompt)

    def workflows(self) -> list[str]:
        out = []
        for m in self.modes.values():
            if m.workflow not in out:
                out.append(m.workflow)
        return out + [w for w in self.alt_workflows if w not in out]


_SOFT = {"layer_mask": "soft", "mask_grow": 8, "mask_blur": 8}

QWEN = Model(
    "qwen", "Qwen2.1",
    "Qwen Image 2.1 Edit: an instruction editor with a very good Generative fill, Remove (works without a prompt), "
    "Expand and whole-image edits. Reference images work with the picture as image 1 and the inserted one as image 2.\n"
    "Base res. 1024 is the best size for it: 1224 and 1536 shift the filled area.",
    {
        "edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, layer_mask="none")),
        "inpaint": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=True, feather_pct=4.0)),
        "outpaint": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, layer_mask="auto")),
        "reference": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, ref_style="simple", ref_cutout=True, layer_mask="auto")),
        "remove": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=True, feather_pct=4.0)),
    })

FLUX2 = Model(
    "flux2", "Flux2Klein",
    "FLUX.2 Klein 9B: whole-image edits, upscale and refine (the Ultra real LoRA is the switch).",
    {
        "edit": Mode("flux2-klein-edit.json", dict(base_res=1224, layer_mask="none")),
        "upscale": Mode("flux2-klein-upscale.json", dict(scale=2.0, turbo=True), PLACEHOLDER),
        "refine": Mode("flux2-klein-upscale.json", dict(turbo=True), PLACEHOLDER),
    })

FLUX3 = Model(
    "flux3", "Flux3Klein",
    "FLUX.3 Klein: whole-image edits, and the SeedVR2 + tiles upscale / refine (the Restore LoRA and the SeedVR2 stage are switches).",
    {
        "edit": Mode("flux3-klein-edit.json", dict(base_res=1224, layer_mask="none")),
        "upscale": Mode("flux3-klein-upscale.json", dict(scale=1.5, turbo=True, stage_on=True), PLACEHOLDER),
        "refine": Mode("flux3-klein-upscale.json", dict(turbo=True, stage_on=True), PLACEHOLDER),
    })

# MOSS: the DMD2 speed LoRA (8 steps, CFG 1.5) is the model's own LoRA; the Lenovo UltraReal LoRA and the skip-layer
# guidance (SLG) are switches that start off until they have been compared.
_MOSS = dict(turbo=True, stage_on=False, stage2_on=False)
MOSS = Model(
    "moss", "MOSS Image",
    "MOSS-Image 5B: a text-to-image model. Text to image (with its own prompt enhancer) and Generative fill with a mask; "
    "Expand is a test. It has no instruction-edit functions (yet). Likes 1.5 to 2 MP. The DMD2 LoRA makes it fast (8 steps, CFG 1.5).",
    {
        "txt2img": Mode("moss-image-t2i.json", {**_MOSS, "base_res": 1280, "layer_mask": "none", "enhance": True}),
        "inpaint": Mode("moss-image-inpaint.json", {**_SOFT, **_MOSS, "base_res": 1216, "context": 0.4}),
        "outpaint": Mode("moss-image-inpaint.json", {**_MOSS, "base_res": 1216, "layer_mask": "auto"}),
    })

FIBO = Model(
    "fibo", "Fibo 2.0 Edit",
    "Fibo 2.0 Edit Turbo: an instruction editor. Fill, Remove, Reference (the simple style works best) and whole-image edits. "
    "The VGL variants (a text model writes the prompt) are chosen under the prompt.",
    {
        "edit": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="none", enhance=False)),
        "inpaint": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "outpaint": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "reference": Mode("fibo2-edit-plain.json", dict(base_res=1024, ref_style="simple", ref_cutout=True, layer_mask="auto", enhance=False)),
        "remove": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
    },
    alt_workflows=("fibo2-edit-vgl-bionic-gemma4-12b.json", "fibo2-edit-vgl-bionic-qwen35-9b.json", "fibo2-edit-vgl-qwen35-convrot.json"),
    llm=(("fibo2-edit-plain.json", "None (your text as typed)"),
         ("fibo2-edit-vgl-bionic-gemma4-12b.json", "Gemma 4 12B (bionic)"),
         ("fibo2-edit-vgl-bionic-qwen35-9b.json", "Qwen 3.5 9B (bionic)"),
         ("fibo2-edit-vgl-qwen35-convrot.json", "Qwen 3.5 9B (native, convrot)")))

MODELS = [QWEN, FLUX2, FLUX3, MOSS, FIBO]
BY_KEY = {m.key: m for m in MODELS}


def model_for_workflow(name: str) -> Model | None:
    """The model a workflow file belongs to (None for a workflow of your own)."""
    return next((m for m in MODELS if name in m.workflows()), None)
