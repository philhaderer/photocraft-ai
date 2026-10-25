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
    prompts: tuple = ()             # (label, text, tip): ready-made prompts, shown as radio buttons next to "Prompt"
    prompt_tip: str = ""            # an orange hint under the prompt field in this mode (the field gets an orange frame)
    run_as: str = ""                # the mode the bridge runs when it is another one (Fibo "Refine" runs as a whole-image edit)
    fixed_prompt: bool = False      # the mode sends a fixed instruction (Remove): the field shows it, read-only
    remove_text: bool = False       # Remove Selection: the field stays usable and takes an optional name of the object ("the dog")


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    tip: str
    modes: dict                     # mode key -> Mode (a mode that is not here is greyed out)
    mode_tips: dict = field(default_factory=dict)   # mode key -> the tooltip of that mode's radio button (this model only)

    def workflows(self) -> list[str]:
        out = []
        for m in self.modes.values():
            if m.workflow not in out:
                out.append(m.workflow)
        return out


_SOFT = {"layer_mask": "soft", "mask_grow": 8, "mask_blur": 8}

# Refine / Upscale (Flux 2 and 3 Klein): the field holds the WHOLE prompt and starts with what the workflow sends by default;
# describing the picture in front of it helps. Flux 2 also offers relight prompts (live tested).
FLUX2_DEFAULT = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition, people, faces and colors exactly as they are."
FLUX3_DEFAULT = "Restore the photo: remove blur, noise and compression artifacts and recover sharp, natural detail, keeping the same composition, people and colors."
RELIGHT_NEUTRAL = "A crystal-clear, high-fidelity photograph of the subject captured under perfectly neutral, even lighting. The scene utilizes soft global illumination to eliminate harsh shadows and high contrast, resulting in a balanced, flat-field exposure. The white balance is calibrated to 5500K (daylight neutral), ensuring absolutely accurate, true-to-life colors with no warm or cool color casts. Photographed with a Sony A7R V using a 55mm f/8 lens for maximum sharpness from edge to edge and zero distortion. The aesthetic is objective, documentary-style, and ultra-realistic. 8k resolution, clean ISO 100, raw output. Remove watermarks and checkerboard patterns."
RELIGHT_STUDIO = "Transform the image into a professionally lit studio portrait with soft, diffused lighting. Remove harsh sunlight, strong contrast, and directional shadows."
FLUX2_REFINE_PROMPTS = (
    ("Default", FLUX2_DEFAULT, "The workflow's own prompt: a sharp, natural photograph of the same scene."),
    ("Neutral", RELIGHT_NEUTRAL, "Relight: soft, even, neutral light without harsh shadows, true-to-life colours."),
    ("Studio portrait", RELIGHT_STUDIO, "Relight: a professionally lit studio portrait with soft, diffused light."),
)
FIBO_REFINE = "relight the scene to natural lighting"
REMOVE_NAME_TIP = "Optional: name what to remove (\"the dog\")."
DESCRIBE_TIP = "Describe the image before this text."
STOCK_PROMPTS = {PLACEHOLDER, FLUX2_DEFAULT, FLUX3_DEFAULT, RELIGHT_NEUTRAL, RELIGHT_STUDIO, FIBO_REFINE}   # texts the window may replace when the mode changes

# The tooltips of the mode buttons are written per model: each tab shows only what is true for its own model.
_TXT = "New picture from text only, as a new layer. A selection is ignored."
_EDIT = "Changes the whole picture from your text (\"make it night\"). A selection is ignored."
_EXPAND = ("Extend the canvas with the Crop tool (Enter) and fill the new area white, then Generate.\n"
           "Text is optional; an empty prompt often works best. Expand large areas in small steps.")
_REMOVE = "Select the object (whole object inside), then Generate. Text is optional: name what to remove (\"the dog\")."
_REF = "Put the reference on its own top layer, select where it goes, then Generate. The layers below are the picture."
_UP = "Enlarges the picture (or selection) into a NEW document. Describe the picture before the prompt text. Max 24 MP."

QWEN = Model(
    "qwen", "Qwen 2.1 Edit",
    "Qwen Image 2.1 Edit: instruction editor, best at Fill Selection, Remove Selection and Expand. Base res. 1024 works best.",
    {
        "txt2img": Mode("qwen-image-21-t2i.json", dict(base_res=1024, turbo=True, layer_mask="none", enhance=False)),
        "edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, layer_mask="none")),
        "inpaint": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=True, feather_pct=4.0)),
        "outpaint": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, layer_mask="auto")),
        "reference": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, ref_style="simple", ref_cutout=True, layer_mask="auto")),
        "remove": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=True, feather_pct=10.0), prompt_tip=REMOVE_NAME_TIP, remove_text=True),
    },
    mode_tips={
        "txt2img": _TXT,
        "edit": _EDIT,
        "inpaint": "Select an area, type what should appear there, then Generate.",
        "outpaint": _EXPAND,
        "reference": _REF,
        "remove": _REMOVE,
    })

FLUX2 = Model(
    "flux2", "Flux 2 Klein Edit",
    "FLUX.2 Klein 9B: whole-image edits, Remove Selection, Expand, Upscale, Refine.",
    {
        "edit": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none")),
        "remove": Mode("flux2-klein-edit.json", dict(_SOFT, base_res=1024, context=0.4, feather_pct=10.0), prompt_tip=REMOVE_NAME_TIP, remove_text=True),
        "outpaint": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="auto")),
        "upscale": Mode("flux2-klein-upscale.json", dict(scale=1.5, turbo=True, context=0.0), FLUX2_DEFAULT, prompt_tip=DESCRIBE_TIP),
        "refine": Mode("flux2-klein-upscale.json", dict(turbo=True, context=0.0), FLUX2_DEFAULT, FLUX2_REFINE_PROMPTS, DESCRIBE_TIP),
    },
    mode_tips={
        "edit": _EDIT + " Nothing happens? Generate again or word it more fully.",
        "remove": _REMOVE + " Works only sometimes: generate again.",
        "outpaint": _EXPAND,
        "upscale": _UP,
        "refine": "Cleans up the picture (or selection) at the same size, as a new layer. Describe the picture before the prompt text.",
    })

FLUX3 = Model(
    "flux3", "Flux 3 Klein Edit",
    "FLUX.3 Klein: text to image, whole-image edits, Remove Selection, Expand, Upscale.",
    {
        "txt2img": Mode("flux3-klein-t2i.json", dict(base_res=1536, layer_mask="none", enhance=False)),
        "edit": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="none")),
        "remove": Mode("flux3-klein-edit.json", dict(_SOFT, base_res=1536, context=0.4, feather_pct=10.0), prompt_tip=REMOVE_NAME_TIP, remove_text=True),
        "outpaint": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="auto")),
        "upscale": Mode("flux3-klein-upscale.json", dict(scale=1.5, turbo=True, stage_on=True, context=0.0), FLUX3_DEFAULT, prompt_tip=DESCRIBE_TIP),
    },
    mode_tips={
        "txt2img": _TXT + " The checkbox lets the prompt upsampler write the long prompt.",
        "edit": _EDIT + " Nothing happens? Generate again or word it more fully.",
        "remove": _REMOVE,
        "outpaint": _EXPAND,
        "upscale": "Enlarges into a NEW document: SeedVR2 cleans, Flux 3 redraws in tiles. Describe the picture before the prompt text. Max 24 MP.",
    })

# MOSS: the DMD2 speed LoRA (8 steps, CFG 1.5) is the model's own LoRA; the Lenovo UltraReal LoRA and the skip-layer
# guidance (SLG) are switches that start on (best result in the live tests); the LLM prompt enhancer starts off.
_MOSS = dict(turbo=True, stage_on=True, stage2_on=True)
MOSS = Model(
    "moss", "MOSS Image",
    "MOSS-Image: text to image and Expand. No edit functions.",
    {
        "txt2img": Mode("moss-image-t2i.json", {**_MOSS, "base_res": 1280, "layer_mask": "none", "enhance": False}),
        "outpaint": Mode("moss-image-inpaint.json", {**_MOSS, "base_res": 1216, "layer_mask": "auto", "match": 0.5}),
    },
    mode_tips={
        "txt2img": _TXT + " The checkbox lets MOSS's own enhancer write the prompt.",
        "outpaint": _EXPAND,
    })

# Krea-2 Turbo: a fast distilled text-to-image model (8 steps, CFG 1). Text to image has the model's own prompt enhancer
# (starts off, like the other models'); Expand redraws the new area with the same mask recipe as MOSS.
KREA2 = Model(
    "krea2", "Krea 2 Turbo",
    "Krea-2 Turbo: fast text to image and Expand.",
    {
        "txt2img": Mode("krea2-turbo-t2i.json", dict(base_res=1024, layer_mask="none", enhance=False)),
        "outpaint": Mode("krea2-turbo-inpaint.json", dict(base_res=1024, layer_mask="auto")),
    },
    mode_tips={
        "txt2img": _TXT + " The checkbox lets Krea's own enhancer write the prompt.",
        "outpaint": _EXPAND,
    })

FIBO = Model(
    "fibo", "Fibo 2.0 Edit",
    "Fibo 2.0 Edit Turbo: instruction editor with all edit functions.",
    {
        "txt2img": Mode("fibo2-t2i.json", dict(base_res=1224, layer_mask="none", enhance=False)),
        "edit": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False)),
        "refine": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), FIBO_REFINE, run_as="edit"),
        "inpaint": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="soft", feather_pct=10.0, enhance=False)),
        "outpaint": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "reference": Mode("fibo2-edit.json", dict(base_res=1024, ref_style="simple", ref_cutout=True, layer_mask="auto", enhance=False)),
        "remove": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="soft", feather_pct=10.0, enhance=False), prompt_tip=REMOVE_NAME_TIP, remove_text=True),
    },
    mode_tips={
        "txt2img": _TXT,
        "edit": _EDIT,
        "refine": "Relights the whole picture as a new layer at the same size. Change the prompt for other edits.",
        "inpaint": "Select an area, type what should appear there (text required), then Generate. To take something away use Remove Selection.",
        "outpaint": _EXPAND,
        "reference": _REF + " Cut the reference out first.",
        "remove": _REMOVE + " Retries up to 3 times if the object stays.",
    })

MODELS = [QWEN, FLUX2, FLUX3, MOSS, KREA2, FIBO]
BY_KEY = {m.key: m for m in MODELS}


def model_for_workflow(name: str) -> Model | None:
    """The model a workflow file belongs to (None for a workflow of your own)."""
    return next((m for m in MODELS if name in m.workflows()), None)
