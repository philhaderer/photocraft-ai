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
    alt_workflows: tuple = ()       # more workflows of this model (listed under Advanced)

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
    "Expand and whole-image edits. Reference images work with the picture as image 1 and the inserted one as image 2.",
    {
        "inpaint": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1224, context=0.4, turbo=True, feather_pct=4.0)),
        "remove": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1224, context=0.4, turbo=True, feather_pct=4.0)),
        "reference": Mode("qwen-image-21-edit.json", dict(base_res=1224, turbo=True, ref_style="simple", ref_cutout=True, layer_mask="auto")),
        "outpaint": Mode("qwen-image-21-edit.json", dict(base_res=1224, turbo=True, layer_mask="auto")),
        "edit": Mode("qwen-image-21-edit.json", dict(base_res=1224, turbo=True, layer_mask="none")),
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

MOSS = Model(
    "moss", "MOSS Image",
    "MOSS-Image 5B: a text-to-image model; here Generative fill with a mask. It has no instruction-edit functions (yet). "
    "Likes 1.5 to 2 MP.",
    {
        "inpaint": Mode("moss-image-inpaint.json", dict(_SOFT, base_res=1216, context=0.4, turbo=False)),
    })

FIBO = Model(
    "fibo", "Fibo 2.0 Edit",
    "Fibo 2.0 Edit Turbo: an instruction editor. Fill, Remove, Reference (the simple style works best) and whole-image edits. "
    "The VGL variants (a text model writes the prompt) are under Advanced > Workflow.",
    {
        "inpaint": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "remove": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "reference": Mode("fibo2-edit-plain.json", dict(base_res=1024, ref_style="simple", ref_cutout=True, layer_mask="auto", enhance=False)),
        "outpaint": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "edit": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="none", enhance=False)),
    },
    alt_workflows=("fibo2-edit-vgl-bionic-gemma4-12b.json", "fibo2-edit-vgl-bionic-qwen35-9b.json", "fibo2-edit-vgl-qwen35-convrot.json"))

MODELS = [QWEN, FLUX2, FLUX3, MOSS, FIBO]
BY_KEY = {m.key: m for m in MODELS}


def model_for_workflow(name: str) -> Model | None:
    """The model a workflow file belongs to (None for a workflow of your own)."""
    return next((m for m in MODELS if name in m.workflows()), None)
