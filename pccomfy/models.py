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
    remove_text: bool = False       # Remove Selection: the field stays usable and takes an optional name of the object ("the dog")
    describe: bool = False          # Expand with Krea 2 / MOSS: a prompt is required, the Describe button under the field writes one
    steps_tip: str = ""             # the tooltip of the Steps field in this mode ("" = none)


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    tip: str
    modes: dict                     # mode key -> Mode (a mode that is not here is greyed out)
    max_refs: int = 0               # Multi Image Edit: how many reference-image slots this model takes (0 = none)
    tag_style: str = ""             # Multi Image Edit: how this model names an image in the prompt; {n} counts from 1 (the picture
                                    # is image 1, the first reference image 2), {i} from 0 ("" = no names)
    requires: tuple = ()            # model detection: the model files this tab needs (file names, as ComfyUI lists them); () = not set yet
    bbox: bool = False              # Multi Image Edit: the BBOX switch (the selection becomes <obj_1>, see bridge.BBOX_SENTENCE); Flux 3 only
    seam: str = "off"               # seam correction in Fill / Remove / Expand: "on" always (one corrected layer), "off" never
                                    # (user 29.10.: Fibo on, the others off; the A/B checkbox was removed 1.11., Qwen fixed off)

    def workflows(self) -> list[str]:
        out = []
        for m in self.modes.values():
            if m.workflow not in out:
                out.append(m.workflow)
        return out


_SOFT = {"layer_mask": "soft", "mask_grow": 8, "mask_blur": 8}

# Refine / Upscale (Flux 2 and 3 Klein): the field holds the WHOLE prompt and starts with what the workflow sends by default;
# describing the picture in front of it helps. Flux 2 also offers relight prompts (live tested).
FLUX2_DEFAULT = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition and colors exactly as they are."
FLUX2_DEFAULT_PREV = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition, and colors exactly as they are."
FLUX2_DEFAULT_OLD = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition, people, faces and colors exactly as they are."
FLUX3_DEFAULT = "Restore the photo: remove blur, noise and compression artifacts and recover sharp, natural detail, keeping the same composition and colors."
RELIGHT_NEUTRAL = "A crystal-clear, high-fidelity photograph of the subject captured under perfectly neutral, even lighting. The scene utilizes soft global illumination to eliminate harsh shadows and high contrast, resulting in a balanced, flat-field exposure. The white balance is calibrated to 5500K (daylight neutral), ensuring absolutely accurate, true-to-life colors with no warm or cool color casts. Photographed with a Sony A7R V using a 55mm f/8 lens for maximum sharpness from edge to edge and zero distortion. The aesthetic is objective, documentary-style, and ultra-realistic. 8k resolution, clean ISO 100, raw output. Remove watermarks and checkerboard patterns."
RELIGHT_STUDIO = "Transform the image into a professionally lit studio portrait with soft, diffused lighting. Remove harsh sunlight, strong contrast, and directional shadows."
FLUX2_REFINE_PROMPTS = (
    ("Default", FLUX2_DEFAULT, "The workflow's own prompt: a sharp, natural photograph of the same scene."),
    ("Neutral", RELIGHT_NEUTRAL, "Relight: soft, even, neutral light without harsh shadows, true-to-life colours."),
    ("Studio portrait", RELIGHT_STUDIO, "Relight: a professionally lit studio portrait with soft, diffused light."),
)
FLUX3_RESTORE = "Restore this old photo: remove scratches, white lines, dust, folds and stains, and bring back sharp facial detail. Keep the people, their faces, their expressions, their poses and the framing exactly unchanged."   # after Pixaroma's "Restore and Colorize" (wording agreed with the user 1.11.)
FLUX3_REFINE_PROMPTS = (
    ("Default", FLUX3_DEFAULT, "The workflow's own prompt: restore sharp, natural detail."),
    ("Restore", FLUX3_RESTORE, "Repair an old or damaged photo: scratches, dust, folds and stains go, faces get their detail back."),
)
FIBO_REFINE = "relight the scene to natural lighting"   # Fibo Refine's old prompt (now FLUX2_DEFAULT, user 28.10.); kept as a stock text
FILL_TIP = "Draw a selection and prompt e.g. “a red flower”. Hide layers from previous results before running again."   # wording from the user (28.10.)
QWEN_SMALL = "Small selections don't work well with Qwen."   # user 30.10.: small fills came out shifted (helikopter.psd)
REMOVE_NAME_TIP = "Optional: name what to remove (\"the dog\")."
REMOVE_AGAIN = "If the first try didn't work, try removing it a second time."   # Fibo Remove, idea of the user (28.10.)
MULTI_TIP = "Place reference images on an image or on an empty white canvas. Example: \"Place the tent from {tag} in the meadow.\""   # {tag}: the model's name for reference image 1 (user 1.11.)
EDIT_TIP = "Describe the result: \u201cReplace the dog with a vase of flowers.\u201d"
# Krea 2 / MOSS Expand (wording chosen by the user 29.10.; A/B test docs/tests/krea-moss-expand-ab.md)
EXPAND_DESCRIBE_TIP = ("This model needs a prompt: describe the surroundings only (place, light, style), not the main subject. "
                       "Describe writes one for you.")
DESCRIBE_TIP = "Add a short description of your image in front of this text."   # Refine and Upscale, wording chosen by the user (28.10.)
T2I_TIP = "Text to image: a completely new image is added to the canvas as a new layer."
FLUX3_DEFAULT_OLD = "Restore the photo: remove blur, noise and compression artifacts and recover sharp, natural detail, keeping the same composition, people and colors."
STOCK_PROMPTS = {FLUX2_DEFAULT_PREV, FLUX2_DEFAULT_OLD, FLUX3_DEFAULT_OLD, PLACEHOLDER, FLUX2_DEFAULT, FLUX3_DEFAULT, FLUX3_RESTORE, RELIGHT_NEUTRAL, RELIGHT_STUDIO, FIBO_REFINE}   # texts the window may replace when the mode changes

# The tooltips of the function buttons: one general text per function, the same for every model (user 28.10.); what
# holds for one model only goes into its tip under the prompt (Mode.prompt_tip). The ranking goes in front (function_tip).
FUNCTION_TIPS = {
    "inpaint": "Select an area, type what should appear there, then Generate.",
    "remove": "Select the object (whole object inside), then Generate. Text is optional: name what to remove (\"the dog\").",
    "multi_edit": ("Edit the picture with reference images in the slots below (drop, paste or add files). "
                   "Name them in the text by their tags. The whole picture changes; a selection is ignored."),
    "outpaint": ("Extend the canvas with the Crop tool (Enter) and fill the new area white, then Generate.\n"
                 "Text is optional; an empty prompt often works best. Expand large areas in small steps."),
    "edit": "Changes the whole picture from your text (\"make it night\"). A selection is ignored.",
    "img2img": "Reworks the picture (or selection) from your text.",
    "upscale": "Enlarges the picture (or selection) into a NEW document, up to 24 MP.",
    "refine": "Cleans up the picture (or selection) at the same size, as a new layer.",
    "txt2img": "New picture from text only, as a new layer. A selection is ignored.",
}
EDIT_AGAIN = "Nothing happens? Generate again or word it more fully."     # Flux 2 and 3 Edit (was in their tooltip)

QWEN = Model(
    "qwen", "Qwen 2.1 Edit",
    "Qwen Image 2.1 Edit: instruction editor, best at Fill Selection, Remove Selection and Expand. Base res. 1024 works best.",
    {
        "txt2img": Mode("qwen-image-21-t2i.json", dict(base_res=1024, turbo=False, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),   # LLM off like the others (user 30.10.)
        "edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=False, layer_mask="none"), prompt_tip=EDIT_TIP),
        "multi_edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=False, layer_mask="none"), prompt_tip=MULTI_TIP, run_as="edit"),
        # soft: opaque over the selection, fading out to the crop's side (Bridge: soft_layer_mask; Fill mask test round 30.10.)
        "inpaint": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=False, feather_pct=4.0), prompt_tip=FILL_TIP + " " + QWEN_SMALL),
        "outpaint": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=False, layer_mask="none")),   # = the old "auto"
        "remove": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=False, feather_pct=10.0), prompt_tip=REMOVE_NAME_TIP, remove_text=True),
    },
    requires=(
        "qwen_image_2.1_int8_convrot.safetensors",
        "qwen_image_2.1_vae_bf16.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=8, tag_style="<image{n}>")

FLUX2 = Model(
    "flux2", "Flux 2 Klein Edit",
    "FLUX.2 Klein 9B: text to image, whole-image edits, Remove Selection, Expand, Upscale, Refine.",
    {
        "txt2img": Mode("flux2-klein-t2i.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),
        "edit": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none"), prompt_tip=EDIT_TIP + " " + EDIT_AGAIN),
        "multi_edit": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none"), prompt_tip=MULTI_TIP, run_as="edit"),
        "remove": Mode("flux2-klein-edit.json", dict(_SOFT, base_res=1024, context=0.4, feather_pct=10.0), prompt_tip=REMOVE_NAME_TIP + " " + REMOVE_AGAIN, remove_text=True),
        "outpaint": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none")),
        "upscale": Mode("flux2-klein-upscale.json", dict(scale=1.5, turbo=True, context=0.0), FLUX2_DEFAULT, prompt_tip=DESCRIBE_TIP),
        "refine": Mode("flux2-klein-upscale.json", dict(turbo=True, context=0.0), FLUX2_DEFAULT, FLUX2_REFINE_PROMPTS, DESCRIBE_TIP),
    },
    requires=(
        "flux-2-klein-9b_int8_convrot.safetensors",
        "qwen_3_8b_fp8mixed.safetensors",
        "flux2-vae.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=3, tag_style="image {n}", seam="off")

FLUX3 = Model(
    "flux3", "Flux 3 Klein Edit",
    "FLUX.3 Klein: text to image, whole-image edits, Remove Selection, Expand, Upscale, Refine.",
    {
        "txt2img": Mode("flux3-klein-t2i.json", dict(base_res=1536, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),
        "edit": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="none"), prompt_tip=EDIT_TIP + " " + EDIT_AGAIN),
        "multi_edit": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="none"), prompt_tip=MULTI_TIP, run_as="edit"),
        "remove": Mode("flux3-klein-edit.json", dict(_SOFT, base_res=1536, context=0.4, feather_pct=10.0), prompt_tip=REMOVE_NAME_TIP, remove_text=True),
        # Expand: its own graph with ausboss' outpaint LoRA (29.10., after Pixaroma's "14. Flux 3 Klein - Outpaint"; without
        # it Flux 3 slid or zoomed the picture instead of filling the margin): grey margin, ~1 megapixel, Context 1.0
        "outpaint": Mode("flux3-klein-outpaint.json", dict(base_res=1024, context=1.0, layer_mask="none")),
        "upscale": Mode("flux3-klein-upscale.json", dict(scale=1.5, turbo=True, stage_on=False, context=0.0), FLUX3_DEFAULT, prompt_tip=DESCRIBE_TIP),
        "refine": Mode("flux3-klein-refine.json", dict(turbo=False, context=0.0), FLUX3_DEFAULT, FLUX3_REFINE_PROMPTS, DESCRIBE_TIP),
    },
    requires=(
        "flux3-image-klein-int8-convrot.safetensors",
        "qwen3vl_4b_int8_convrot.safetensors",
        "flux2-vae.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=3, tag_style="<ref_image_{i}>", seam="off", bbox=True)

# MOSS: the DMD2 speed LoRA (8 steps, CFG 1.5) is the model's own LoRA; the Lenovo UltraReal LoRA and the skip-layer
# guidance (SLG) are switches that start on (best result in the live tests); the LLM prompt enhancer starts off.
_MOSS = dict(turbo=True, stage_on=True, stage2_on=True)
MOSS_STEPS_TIP = "Turn up the steps to 35 for best results."     # wording of the user (29.10.), 35 after the CFG test
_MOSS_EDIT = dict(base_res=1024, layer_mask="none")
_MOSS_INPAINT = {**_MOSS, "turbo": False, "stage2_on": False, "base_res": 1216, "layer_mask": "soft", "mask_grow": 8, "mask_blur": 16,
                 "context": 0.4}
MOSS_EDIT_TIP = ("Describe the change: “Change only the X to Y. Keep the rest unchanged.”")   # wording of the LoRA's template; proposal, the user decides
MOSS = Model(
    "moss", "MOSS Image",
    "MOSS-Image: text to image, Edit Canvas, Multi Image Edit, Remove Selection (edit LoRA), Fill and Expand (Inpainting v10).",
    {
        # Text to image starts without DMD2 and without SLG, no LLM: the user's live test 29.10. (with DMD2 or SLG the photos
        # looked artificial, with the LLM prompt too). Without DMD2 the workflow runs 35 steps at CFG 3.0 (pc_no_lora; blind
        # test docs/tests/moss-cfg.md)
        "txt2img": Mode("moss-image-t2i.json", {**_MOSS, "turbo": False, "stage2_on": False, "base_res": 1280,
                                                "layer_mask": "none", "enhance": False},
                        prompt_tip=T2I_TIP, steps_tip=MOSS_STEPS_TIP),
        # Edit (1.11.): the edit LoRA on the same checkpoint, 30 steps at CFG 4 (euler / normal) as the LoRA's author ships it;
        # no speed LoRA. The workflow takes no mask, so Remove Selection works like Qwen's (red outline + instruction).
        "edit": Mode("moss-image-edit.json", _MOSS_EDIT, prompt_tip=MOSS_EDIT_TIP),
        "multi_edit": Mode("moss-image-edit.json", _MOSS_EDIT, prompt_tip=MULTI_TIP, run_as="edit"),
        "remove": Mode("moss-image-edit.json", dict(_SOFT, base_res=1024, context=0.4, feather_pct=10.0),
                       prompt_tip=REMOVE_NAME_TIP, remove_text=True),
        # Fill and Expand (1.11., to test): MOSS Inpainting v10's recipe: 25 steps, CFG 2.5, er_sde / simple, no DMD2, UltraReal on,
        # mask grown by 8 and softened by 16; the plugin cuts out the part (Context 0.4), the tick "v10 graph" lets the graph do it
        "inpaint": Mode("moss-image-inpaint.json", _MOSS_INPAINT, prompt_tip=FILL_TIP),
        "outpaint": Mode("moss-image-inpaint.json", {**_MOSS_INPAINT, "match": 0.5}, prompt_tip=EXPAND_DESCRIBE_TIP, describe=True),
    },
    requires=(
        "moss_image_sft_int8_convrot.safetensors",
        "qwen3.5_9b_w4a8_gptq.safetensors",
        "flux2-vae_small.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=3, tag_style="image {n}", seam="off")

# Krea-2 Turbo: a fast distilled text-to-image model (8 steps, CFG 1). Text to image has the model's own prompt enhancer
# (starts off, like the other models').
KREA2 = Model(
    "krea2", "Krea 2 Turbo",
    "Krea-2 Turbo: fast text to image.",
    {
        "txt2img": Mode("krea2-turbo-t2i.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),
    },
    requires=(
        "krea2_turbo_int8_convrot.safetensors",
        "qwen3vl_4b_fp8_scaled.safetensors",
        "qwen_image_vae.safetensors",
    ))   # the model files this tab needs (details per mode: manifest.py)

# Expand with Krea 2 and MOSS was switched off (user 29.10.; MOSS came back 1.11. with the Inpainting v10 recipe, see MOSS above): in a blind test with the user's own pictures
# (docs/tests/expand-seam-testrunde.md) only 2 of 64 Krea 2 and 10 of 64 MOSS results were good, also with a description
# of the surroundings, a wider overlap, the seam correction or a second run over the border. The modes are kept here,
# with the Describe button they used, so they can come back when a better recipe exists (idea: Krea 2 AnyPaint LoRA).
PARKED_EXPAND = {
    "krea2": Mode("krea2-turbo-inpaint.json", dict(base_res=1024, layer_mask="soft"),
                  prompt_tip=EXPAND_DESCRIBE_TIP, describe=True),
}
# their graph files stay in the workflows folder but are not offered in the Workflow list: picked there they counted as a
# workflow of your own ("Image -> image" appeared, user 29.10.)
PARKED_WORKFLOWS = {m.workflow for m in PARKED_EXPAND.values()}

FIBO = Model(
    "fibo", "Fibo 2.0 Edit Turbo",
    "Instruction editor with all edit functions.",
    {
        "txt2img": Mode("fibo2-t2i.json", dict(base_res=1224, layer_mask="none", enhance=False, sharpen=0.2), prompt_tip=T2I_TIP),   # Sharpen 20 % (user 28.10.)
        "edit": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=EDIT_TIP),
        "multi_edit": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=MULTI_TIP, run_as="edit"),
        "refine": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False, sharpen=0.1), FLUX2_DEFAULT, run_as="edit",
                       prompt_tip=DESCRIBE_TIP + " Change the prompt for other edits."),   # Sharpen 10 % (final, user 31.10.)
        "inpaint": Mode("fibo2-edit.json", dict(base_res=1024, context=0.1, layer_mask="soft", feather_pct=10.0, enhance=False), prompt_tip=FILL_TIP),   # Context 0.1 chosen by the user 1.11. (was 0.4 from the test round 28.10.); Edge feather 10 % stays
        "outpaint": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False)),
        "remove": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="soft", feather_pct=10.0, enhance=False), prompt_tip=REMOVE_NAME_TIP + " " + REMOVE_AGAIN, remove_text=True),
    },
    requires=(
        "fibo2_edit_turbo_int8_convrot.safetensors",
        "qwen3vl_4b_int8_convrot.safetensors",
        "flux2-vae.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=2, tag_style="<image_{n}>", seam="on")

MODELS = [FLUX3, FLUX2, QWEN, FIBO, KREA2, MOSS]      # the order of the tabs
BY_KEY = {m.key: m for m in MODELS}

# The user's ranking of the models per function (best first), shown at the start of each function's tooltip while
# testing (user 28.10.: "keep the ranking in view"); the user tells changes. Also the order for Easy Mode (PLAN.md).
# A function missing here has no ranking yet.
RANKING = {
    "inpaint": ("fibo", "qwen"),            # E2 test round 28.10.: "Fibo is better overall"
    "remove": ("fibo", "qwen"),
    "outpaint": ("flux2", "flux3", "qwen", "fibo"),   # user 28.10.: Flux 2 very good, Flux 3 and Qwen too; Krea 2 / MOSS off 29.10.
    # the rest is the order of Easy Mode (user 31.10.); Refine and Multi Image Edit are accepted for now, still being checked (1.11.)
    "txt2img": ("flux3", "moss", "flux2", "qwen", "fibo"),
    "edit": ("flux3", "qwen", "flux2", "fibo"),
    "upscale": ("flux3", "flux2"),
    "refine": ("fibo", "flux2", "flux3"),
    "multi_edit": ("flux3", "flux2", "qwen", "fibo"),
}
SHORT = {"flux3": "Flux 3", "flux2": "Flux 2", "qwen": "Qwen", "fibo": "Fibo", "krea2": "Krea 2", "moss": "MOSS"}


def ranking_text(mode: str) -> str:
    """'Ranking: 1. Fibo, 2. Qwen (not ranked: Flux 3, Flux 2).' for a function's tooltip; '' when no model offers it."""
    offered = [m.key for m in MODELS if mode in m.modes]
    if not offered:
        return ""
    ranked = [k for k in RANKING.get(mode, ()) if k in offered]
    rest = [SHORT[k] for k in offered if k not in ranked]
    if not ranked:
        return "Ranking: not set yet."
    text = "Ranking: " + ", ".join(f"{i}. {SHORT[k]}" for i, k in enumerate(ranked, 1))
    return text + (f" (not ranked: {', '.join(rest)})." if rest else ".")


def function_tip(mode: str, text: str) -> str:
    """A function's tooltip with the ranking in front."""
    r = ranking_text(mode)
    return f"{r}\n{text}" if r else text


def model_for_workflow(name: str) -> Model | None:
    """The model a workflow file belongs to (None for a workflow of your own)."""
    return next((m for m in MODELS if name in m.workflows()), None)
