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


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    tip: str
    modes: dict                     # mode key -> Mode (a mode that is not here is greyed out)
    alt_workflows: tuple = ()       # more workflows of this model
    llm: tuple = ()                 # (workflow, label) of the text models that can write the prompt (a drop-down under the prompt)
    mode_tips: dict = field(default_factory=dict)   # mode key -> the tooltip of that mode's radio button (this model only)

    def workflows(self) -> list[str]:
        out = []
        for m in self.modes.values():
            if m.workflow not in out:
                out.append(m.workflow)
        return out + [w for w in self.alt_workflows if w not in out]


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
DESCRIBE_TIP = "Describe the image for better results in front of the prompt."
STOCK_PROMPTS = {PLACEHOLDER, FLUX2_DEFAULT, FLUX3_DEFAULT, RELIGHT_NEUTRAL, RELIGHT_STUDIO}   # texts the window may replace when the mode changes

# The tooltips of the mode buttons are written per model: each tab shows only what is true for its own model.
_TXT = "Creates a new picture from text only, as a new layer in the size of the canvas. A selection is ignored."
_EDIT = ("Changes the WHOLE picture from your text, like talking to an image editor (\"make it night\", \"turn the car red\"). "
         "A selection is ignored.")
_EXPAND = ("Extend the canvas with the Crop tool (confirm with Enter), then Generate: the empty area is filled.\n"
           "The text is optional and describes what the new area shows; an empty prompt often fills best.\n"
           "Large extensions drift in style and tone at the seam: extend in smaller steps and repeat.")
_REMOVE = "Select the object to remove (tightly, but with the whole object inside), then Generate. No text needed."

QWEN = Model(
    "qwen", "Qwen2.1",
    "Qwen Image 2.1 Edit: an instruction editor with a very good Generative fill, Remove (works without a prompt), "
    "Expand and whole-image edits. Reference images work with the picture as image 1 and the inserted one as image 2.\n"
    "Base res. 1024 is the best size for it: 1224 and 1536 shift the filled area.",
    {
        "txt2img": Mode("qwen-image-21-t2i.json", dict(base_res=1024, turbo=True, layer_mask="none", enhance=False)),
        "edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, layer_mask="none")),
        "inpaint": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=True, feather_pct=4.0)),
        "outpaint": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, layer_mask="auto")),
        "reference": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=True, ref_style="simple", ref_cutout=True, layer_mask="auto")),
        "remove": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=True, feather_pct=10.0)),
    },
    mode_tips={
        "txt2img": _TXT,
        "edit": _EDIT,
        "inpaint": "Select an area (Lasso / Rectangular Marquee), type what should appear there (\"a helicopter on the meadow\"), "
                   "then Generate.\nQwen redraws the area in its surroundings; the text is wrapped in a fixed instruction.",
        "outpaint": _EXPAND,
        "reference": "Insert a person or object with the look of another picture.\n"
                     "1. Put it on its own layer ABOVE everything else.\n2. Select where it should stand.\n3. Generate.\n"
                     "The top layer is the reference (image 2); the visible layers below are the picture (image 1). "
                     "\"Cut out the reference\" adds a sentence that removes its background first.",
        "remove": _REMOVE + "\nThe object is erased and the scenery behind it painted.",
    })

FLUX2 = Model(
    "flux2", "Flux2Klein",
    "FLUX.2 Klein 9B: whole-image edits, Remove, Expand (a test), upscale and refine (the Ultra real LoRA is the switch).",
    {
        "edit": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none")),
        "remove": Mode("flux2-klein-edit.json", dict(_SOFT, base_res=1024, context=0.4, feather_pct=10.0)),   # a test
        "outpaint": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="auto")),
        "upscale": Mode("flux2-klein-upscale.json", dict(scale=1.5, turbo=True, context=0.0), FLUX2_DEFAULT, prompt_tip=DESCRIBE_TIP),
        "refine": Mode("flux2-klein-upscale.json", dict(turbo=True, context=0.0), FLUX2_DEFAULT, FLUX2_REFINE_PROMPTS, DESCRIBE_TIP),
    },
    mode_tips={
        "edit": _EDIT + "\nIf nothing happens, generate again (new seed) or word it more fully (\"Remove all buildings and fill with sky\").",
        "remove": _REMOVE + "\nA test for Flux 2 Klein: it is an editor, so the selection is shown to it as a red outline.",
        "outpaint": _EXPAND + "\nA test for Flux 2 Klein.",
        "upscale": "Enlarges the picture (or the selection) by the factor and opens the result as a NEW document; your document stays as it is.\n"
                   "The prompt starts with the workflow's own sentence; describe the picture in front of it for better results.\n"
                   "Results above 24 megapixels are refused.",
        "refine": "Cleans up the picture (or the selection) at the SAME size and puts the result on a new layer.\n"
                  "The prompt starts with the workflow's own sentence; describe the picture in front of it for better results. "
                  "Neutral / Studio portrait relight the picture.",
    })

FLUX3 = Model(
    "flux3", "Flux3Klein",
    "FLUX.3 Klein: text to image (with the Flux 3 prompt upsampler, switchable) and whole-image edits (base res 1536), Remove, Expand (a test), and the SeedVR2 + tiles upscale / refine (the Restore LoRA and the SeedVR2 stage are switches).",
    {
        "txt2img": Mode("flux3-klein-t2i.json", dict(base_res=1536, layer_mask="none", enhance=False)),
        "edit": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="none")),
        "remove": Mode("flux3-klein-edit.json", dict(_SOFT, base_res=1536, context=0.4, feather_pct=10.0)),   # a test
        "outpaint": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="auto")),
        "upscale": Mode("flux3-klein-upscale.json", dict(scale=1.5, turbo=True, stage_on=True, context=0.0), FLUX3_DEFAULT, prompt_tip=DESCRIBE_TIP),
        "refine": Mode("flux3-klein-upscale.json", dict(turbo=True, stage_on=True, context=0.0), FLUX3_DEFAULT, prompt_tip=DESCRIBE_TIP),
    },
    mode_tips={
        "txt2img": _TXT + "\nThe Flux 3 prompt upsampler (the checkbox under the prompt) can write the long prompt from your short text.",
        "edit": _EDIT + "\nIf nothing happens, generate again (new seed) or word it more fully (\"Remove all buildings and fill with sky\").",
        "remove": _REMOVE + "\nA test for Flux 3 Klein: it is an editor, so the selection is shown to it as a red outline.",
        "outpaint": _EXPAND + "\nA test for Flux 3 Klein.",
        "upscale": "Enlarges the picture (or the selection) by the factor and opens the result as a NEW document; your document stays as it is.\n"
                   "SeedVR2 cleans the photo, Flux 3 Klein redraws it in tiles. The prompt starts with the workflow's own sentence; "
                   "describe the picture in front of it for better results.\nResults above 24 megapixels are refused.",
        "refine": "Cleans up the picture (or the selection) at the SAME size and puts the result on a new layer.\n"
                  "Same workflow as Upscale at factor 1. The prompt starts with the workflow's own sentence; "
                  "describe the picture in front of it for better results.",
    })

# MOSS: the DMD2 speed LoRA (8 steps, CFG 1.5) is the model's own LoRA; the Lenovo UltraReal LoRA and the skip-layer
# guidance (SLG) are switches that start on (best result in the live tests); the LLM prompt enhancer starts off.
_MOSS = dict(turbo=True, stage_on=True, stage2_on=True)
MOSS = Model(
    "moss", "MOSS Image",
    "MOSS-Image 5B: a text-to-image model. Text to image (with its own prompt enhancer), Generative fill and Expand "
    "(the same model redraws the masked area). It has no instruction-edit functions (yet). Likes 1.5 to 2 MP. The DMD2 LoRA makes it fast (8 steps, CFG 1.5).",
    {
        "txt2img": Mode("moss-image-t2i.json", {**_MOSS, "base_res": 1280, "layer_mask": "none", "enhance": False}),
        "inpaint": Mode("moss-image-inpaint.json", {**_MOSS, "base_res": 1216, "context": 0.4, "layer_mask": "soft", "mask_grow": 8,
                                                    "mask_blur": 8, "feather_pct": 4.0, "match": 0.5}),
        "outpaint": Mode("moss-image-inpaint.json", {**_MOSS, "base_res": 1216, "layer_mask": "auto", "match": 0.5}),
    },
    mode_tips={
        "txt2img": _TXT + "\nIts own prompt enhancer can write the long English caption MOSS likes.",
        "inpaint": "Select an area (Lasso / Rectangular Marquee), type what should appear there (\"a red silk scarf\"), then Generate.\n"
                   "MOSS redraws only the masked area and keeps the rest of the crop; the result is pasted with a soft edge.",
        "outpaint": _EXPAND,
    })

FIBO = Model(
    "fibo", "Fibo 2.0 Edit",
    "Fibo 2.0 Edit Turbo: an instruction editor. Fill, Remove, Reference (the simple style works best) and whole-image edits. "
    "The VGL variants (a text model writes the prompt) are chosen under the prompt.",
    {
        "edit": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="none", enhance=False)),
        "inpaint": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="soft", feather_pct=10.0, enhance=False)),
        "outpaint": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="auto", enhance=False)),
        "reference": Mode("fibo2-edit-plain.json", dict(base_res=1024, ref_style="simple", ref_cutout=True, layer_mask="auto", enhance=False)),
        "remove": Mode("fibo2-edit-plain.json", dict(base_res=1024, layer_mask="soft", feather_pct=10.0, enhance=False)),
    },
    alt_workflows=("fibo2-edit-vgl-bionic-gemma4-12b.json", "fibo2-edit-vgl-bionic-qwen35-9b.json", "fibo2-edit-vgl-qwen35-convrot.json"),
    llm=(("fibo2-edit-plain.json", "None (your text as typed)"),
         ("fibo2-edit-vgl-bionic-gemma4-12b.json", "Gemma 4 12B (bionic)"),
         ("fibo2-edit-vgl-bionic-qwen35-9b.json", "Qwen 3.5 9B (bionic)"),
         ("fibo2-edit-vgl-qwen35-convrot.json", "Qwen 3.5 9B (native, convrot)")),
    mode_tips={
        "edit": _EDIT,
        "inpaint": "Select an area (Lasso / Rectangular Marquee), type what should appear there (\"a helicopter on the meadow\"), "
                   "then Generate. A text is required; to take something away use Remove.\n"
                   "The selection is drawn into the picture as a red outline and your text is wrapped in a fixed instruction "
                   "(place it only inside the outline), so the object lands where you marked.\n"
                   "With a text model under the prompt, it writes the long prompt from your text (about 25 s slower).",
        "outpaint": _EXPAND,
        "reference": "Insert a person or object with the look of a picture (e.g. a Viking).\n"
                     "1. Put it on its own layer ABOVE everything else (cut out, transparent).\n2. Select where it should stand.\n3. Generate.\n"
                     "The top layer is the reference; the visible layers below are the picture. "
                     "\"Rough placement\" (classic style) pastes a scaled copy into the selection so the position is kept. "
                     "Your text is added to a fixed instruction (\"standing, facing left\").",
        "remove": _REMOVE + "\nA red outline is drawn into the picture the model gets (never into your document) and a fixed "
                  "instruction says: erase everything inside it and paint the scenery behind. "
                  "If the object is still there the plugin tries again by itself (up to 3 times, new seed each).\n"
                  "If a part of the object is already gone, include what is left in the selection.",
    })

MODELS = [QWEN, FLUX2, FLUX3, MOSS, FIBO]
BY_KEY = {m.key: m for m in MODELS}


def model_for_workflow(name: str) -> Model | None:
    """The model a workflow file belongs to (None for a workflow of your own)."""
    return next((m for m in MODELS if name in m.workflows()), None)
