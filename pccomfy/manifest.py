"""The model manifest: which files each tab needs, and where a user gets them.

Pure data, no ComfyUI and no Tk. Three levels per tab (decided with the user, see PLAN.md task 6 to 8):

* ``required``: files the whole tab needs. When one is missing the tab is greyed out.
* ``modes[mode].requires``: extra files of one mode. When one is missing only that mode is greyed out.
* ``optional`` (tab or mode): switches and helpers (speed LoRAs, prompt enhancers). A missing one is only a note.

The file names are the ones the shipped ``workflows/*.json`` load (checked by tests/test_detection.py). The tab level
``required`` set is mirrored in ``models.Model.requires`` (the same names, ``tab_required``); a test keeps the two equal.
Download links are the ones collected in the project notes ("shipping"); an empty link means: source not known yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# kind -> (loader node class, input field, folder inside ComfyUI's models folder)
KINDS = {
    "unet": ("UNETLoader", "unet_name", "diffusion_models"),
    "clip": ("CLIPLoader", "clip_name", "text_encoders"),
    "vae": ("VAELoader", "vae_name", "vae"),
    "lora": ("LoraLoaderModelOnly", "lora_name", "loras"),
}
KIND_LABEL = {"unet": "Diffusion model", "clip": "Text encoder", "vae": "VAE", "lora": "LoRA"}


@dataclass(frozen=True)
class File:
    name: str                       # as ComfyUI lists it (a LoRA carries its sub-folder, "Moss\\lora_dmd2.safetensors")
    kind: str                       # key of KINDS
    url: str = ""                   # where to get it ("" = not known yet)
    note: str = ""                  # licence, gated, "likely, not confirmed" ...
    aliases: tuple = ()             # other names the same file is known under

    @property
    def folder(self) -> str:
        return KINDS[self.kind][2]

    @property
    def target(self) -> str:
        """Where to put it, relative to ComfyUI's models folder (Windows spelling)."""
        sub = self.name.replace("/", "\\").rpartition("\\")[0]
        return "models\\" + self.folder + (("\\" + sub) if sub else "")


_HF = "https://huggingface.co/"
_LIST = [
    # diffusion models
    File("flux3-image-klein-int8-convrot.safetensors", "unet", _HF + "black-forest-labs/flux-3-image-klein-comfy", "gated: login and licence acceptance (FLUX Kommunity License v1.0)"),
    File("flux-2-klein-9b-int8-ConvRot-comfyui.safetensors", "unet", _HF + "Sakujo/FLUX.2-Klein-9B-INT8-ConvRot"),
    File("qwen_image_2.1_int8_convrot.safetensors", "unet", _HF + "Comfy-Org/Qwen-Image-2.1", "licence qwen-research"),
    File("fibo2_edit_turbo_int8_convrot.safetensors", "unet"),
    File("krea2_turbo_int8_convrot.safetensors", "unet"),
    File("moss_image_sft_int8_convrot.safetensors", "unet", _HF + "Comfy-Org/MOSS-Image"),
    File("seedvr2_3b_int8_convrot.safetensors", "unet", _HF + "Comfy-Org/SeedVR2"),
    # text encoders
    File("qwen_3_8b_fp8mixed.safetensors", "clip", _HF + "Comfy-Org/flux2-klein-9B"),
    File("qwen3vl_4b_int8_convrot.safetensors", "clip", _HF + "Comfy-Org/Fibo-2.0"),
    File("qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors", "clip", _HF + "black-forest-labs/flux-3-image-klein-comfy"),
    File("qwen3vl_8b_fp8_scaled.safetensors", "clip", _HF + "Comfy-Org/Qwen3-VL"),
    File("qwen3vl_8b_int8_convrot.safetensors", "clip"),
    File("qwen3.5_9b_w4a8_gptq.safetensors", "clip", _HF + "Comfy-Org/MOSS-Image"),
    File("qwen3.5_9b_int8_convrot.safetensors", "clip"),
    File("qwen3vl_4b_fp8_scaled.safetensors", "clip"),
    # VAEs
    File("flux2-vae.safetensors", "vae", _HF + "Comfy-Org/flux2-dev"),
    File("flux2-vae_small.safetensors", "vae", _HF + "Comfy-Org/MOSS-Image"),
    File("qwen_image_2.1_vae_bf16.safetensors", "vae", _HF + "Comfy-Org/Qwen-Image-2.1"),
    File("qwen_image_vae.safetensors", "vae"),
    File("seedvr2_ema_vae_fp16.safetensors", "vae", _HF + "Comfy-Org/SeedVR2", aliases=("ema_vae_fp16.safetensors",)),
    # LoRAs
    File("qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors", "lora", _HF + "Comfy-Org/Qwen-Image-2.1"),
    File("Flux 2\\ultra_real_v4.safetensors", "lora", "https://civitai.com/models/2462105", "likely the Civitai LoRA 'UltraReal - Krea2, Klein9b' (not confirmed)"),
    File("Moss\\lora_dmd2.safetensors", "lora", _HF + "lodestones/MOSS-Image-SFT-8-steps-dmd", "plausible: the repo's lora.safetensors, renamed"),
    File("Moss\\lenovo_moss.safetensors", "lora"),
]
FILES: dict[str, File] = {f.name: f for f in _LIST}


@dataclass(frozen=True)
class ModeSpec:
    requires: tuple = ()            # extra files this mode needs on top of the tab's
    optional: tuple = ()            # files of switches that belong to this mode
    nodes: tuple = ()               # node classes this mode needs (checked against ComfyUI's /object_info)


@dataclass(frozen=True)
class TabSpec:
    required: tuple                 # files the whole tab needs
    modes: dict = field(default_factory=dict)   # mode key -> ModeSpec (a mode that is not here has no extras)
    optional: tuple = ()            # files of switches that belong to the whole tab


_UPS = "flux2-vae.safetensors"
_FLUX3_UP_NODES = ("AUSBOSS_NODES_TiledUpscale", "AUSBOSS_NODES_TiledUpscaleStitch", "AUSBOSS_NODES_LoraLoader",
                   "AUSBOSS_NODES_Seed", "AUSBOSS_NODES_Text", "AUSBOSS_NODES_MathExpression", "AUSBOSS_NODES_ImageResize",
                   "SeedVR2Preprocess", "SeedVR2Conditioning", "SeedVR2PostProcessing")
_ULTRA = ("Flux 2\\ultra_real_v4.safetensors",)
_UPSAMPLER = "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors"

TABS: dict[str, TabSpec] = {
    "flux3": TabSpec(
        required=("flux3-image-klein-int8-convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", _UPS),
        modes={
            "txt2img": ModeSpec(optional=(_UPSAMPLER,)),
            "upscale": ModeSpec(requires=("seedvr2_3b_int8_convrot.safetensors", "seedvr2_ema_vae_fp16.safetensors"),
                                nodes=_FLUX3_UP_NODES),
        }),
    "flux2": TabSpec(
        required=("flux-2-klein-9b-int8-ConvRot-comfyui.safetensors", "qwen_3_8b_fp8mixed.safetensors", _UPS),
        modes={
            "txt2img": ModeSpec(optional=(_UPSAMPLER,)),
            "upscale": ModeSpec(requires=_ULTRA),
            "refine": ModeSpec(requires=_ULTRA),
        }),
    "qwen": TabSpec(
        required=("qwen_image_2.1_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"),
        modes={
            # the text-to-image graph loads another text encoder than the edit graph
            "txt2img": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",), optional=("qwen3.5_9b_w4a8_gptq.safetensors",)),
            "edit": ModeSpec(requires=("qwen3vl_8b_fp8_scaled.safetensors",)),
            "inpaint": ModeSpec(requires=("qwen3vl_8b_fp8_scaled.safetensors",)),
            "outpaint": ModeSpec(requires=("qwen3vl_8b_fp8_scaled.safetensors",)),
            "reference": ModeSpec(requires=("qwen3vl_8b_fp8_scaled.safetensors",)),
            "remove": ModeSpec(requires=("qwen3vl_8b_fp8_scaled.safetensors",)),
        },
        optional=("qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors",)),
    "fibo": TabSpec(
        required=("fibo2_edit_turbo_int8_convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", _UPS),
        optional=("qwen3.5_9b_int8_convrot.safetensors",)),      # the native VGL prompt writer (LLM prompt enhancement)
    "krea2": TabSpec(
        required=("krea2_turbo_int8_convrot.safetensors", "qwen3vl_4b_fp8_scaled.safetensors", "qwen_image_vae.safetensors")),
    "moss": TabSpec(
        required=("moss_image_sft_int8_convrot.safetensors", "qwen3.5_9b_w4a8_gptq.safetensors", "flux2-vae_small.safetensors"),
        optional=("Moss\\lora_dmd2.safetensors", "Moss\\lenovo_moss.safetensors")),
}


def tab_required(key: str) -> tuple:
    """The files a whole tab needs (what ``models.Model.requires`` carries)."""
    return TABS[key].required if key in TABS else ()


def mode_extra(key: str, mode: str) -> tuple:
    t = TABS.get(key)
    return t.modes[mode].requires if t and mode in t.modes else ()


def mode_required(key: str, mode: str) -> tuple:
    """Everything one mode needs: the tab's files plus the mode's own."""
    return tab_required(key) + mode_extra(key, mode)


def mode_optional(key: str, mode: str) -> tuple:
    t = TABS.get(key)
    if t is None:
        return ()
    return t.optional + (t.modes[mode].optional if mode in t.modes else ())


def mode_nodes(key: str, mode: str) -> tuple:
    t = TABS.get(key)
    return t.modes[mode].nodes if t and mode in t.modes else ()


# node class prefix -> (pack, where to get it). Only what the shipped workflows use.
NODE_PACKS = (
    ("AUSBOSS_NODES_", "ComfyUI-AusBoss (version 2.13.0 or newer)", "https://github.com/ausboss/ComfyUI-AusBoss"),
    ("SeedVR2", "ComfyUI itself (SeedVR2 nodes): update ComfyUI", "https://github.com/comfyanonymous/ComfyUI"),
    ("VGLBionic", "ComfyUI-VGL-Bionic (not published yet)", ""),
)


def node_pack(cls: str) -> tuple[str, str] | None:
    for prefix, pack, url in NODE_PACKS:
        if cls.startswith(prefix):
            return pack, url
    return None


# Shown in the settings overlay (credits stay mandatory, see CLAUDE.md "Release 1 scope").
CONTRIBUTORS = (
    ("Peszemeszek", "photocraft-comfyui-bridge, the upstream this plugin is forked from (MIT OR Apache-2.0)", "https://github.com/Peszemeszek/photocraft-comfyui-bridge"),
    ("ComfyUI", "the node-based engine behind every generation", "https://github.com/comfyanonymous/ComfyUI"),
    ("Comfy-Org", "ComfyUI-ready model files: Qwen-Image 2.1, Qwen3-VL, FLUX.2, MOSS-Image, SeedVR2, Fibo 2.0", "https://huggingface.co/Comfy-Org"),
    ("Black Forest Labs", "FLUX.2 Klein and FLUX.3 Klein", "https://huggingface.co/black-forest-labs"),
    ("Qwen team (Alibaba)", "Qwen-Image 2.1 and the Qwen text encoders", "https://huggingface.co/Qwen"),
    ("Bria", "Fibo 2.0 Edit and the VGL prompt format", "https://huggingface.co/briaai"),
    ("OpenMOSS", "MOSS-Image", "https://huggingface.co/OpenMOSS-Team"),
    ("Krea", "Krea 2 Turbo", "https://www.krea.ai"),
    ("ausboss", "ComfyUI-AusBoss (tiled upscale nodes) and the FLUX.3 Klein Restore LoRA", "https://github.com/ausboss/ComfyUI-AusBoss"),
    ("lodestones", "MOSS-Image 8-step DMD2 LoRA", "https://huggingface.co/lodestones"),
)
