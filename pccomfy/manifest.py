"""The model manifest: which files each tab needs, and where a user gets them.

Pure data, no ComfyUI and no Tk. Three levels per tab (decided with the user, see PLAN.md task 6 to 8):

* ``required``: files the whole tab needs. When one is missing the tab is greyed out.
* ``modes[mode].requires``: extra files of one mode. When one is missing only that mode is greyed out.
* ``optional`` (tab or mode): switches and helpers (speed LoRAs, prompt enhancers). A missing one is only a note.

The file names are the ones the shipped ``workflows/*.json`` load (checked by tests/test_detection.py). The tab level
``required`` set is mirrored in ``models.Model.requires`` (the same names, ``tab_required``); a test keeps the two equal.
Download links are direct file links (Hugging Face ``resolve/main``, Civitai download API), each checked on 2026-10-27
against the user's working copy by size and, where the name was not unique, by SHA256; the table with licences is
``docs/model-downloads.md``. An empty link means: no public source right now.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

# kind -> (loader node class, input field, folder inside ComfyUI's models folder)
KINDS = {
    "unet": ("UNETLoader", "unet_name", "diffusion_models"),
    "clip": ("CLIPLoader", "clip_name", "text_encoders"),
    "vae": ("VAELoader", "vae_name", "vae"),
    "lora": ("LoraLoaderModelOnly", "lora_name", "loras"),
    "preview": ("", "", "vae_approx"),       # live preview decoders (TAESD): no loader node, ComfyUI lists /models/vae_approx
    "bg_removal": ("LoadBackgroundRemovalModel", "bg_removal_name", "background_removal"),   # "Cut out" in the reference slots
}
# helpers several models share, listed apart in the settings window as "Additional models" (user 30.10.), with their use
ADDITIONAL_KINDS = {"bg_removal": "Cut out in Multi Image Edit", "preview": "Live preview"}
KIND_LABEL = {"unet": "Diffusion model", "clip": "Text encoder", "vae": "VAE", "lora": "LoRA", "preview": "Preview decoder",
              "bg_removal": "Background removal"}


@dataclass(frozen=True)
class File:
    name: str                       # as ComfyUI lists it (a LoRA carries its sub-folder, "Moss\\lora_dmd2.safetensors")
    kind: str                       # key of KINDS
    url: str = ""                   # direct download link ("" = no public source right now)
    note: str = ""                  # licence, gated, "likely, not confirmed" ...
    aliases: tuple = ()             # other names the same file is known under
    size: int = 0                   # bytes, as the source serves it (0 = not known)
    sha256: str = ""                # the SHA-256 the source publishes ("" = none published); set from _SHA256 below

    @property
    def size_text(self) -> str:
        """"9.4 GB", "165 MB" ("" when not known)."""
        if not self.size:
            return ""
        return f"{self.size / 1e9:.1f} GB" if self.size >= 1e9 else f"{self.size / 1e6:.0f} MB"

    @property
    def folder(self) -> str:
        return KINDS[self.kind][2]

    @property
    def target(self) -> str:
        """Where to put it, relative to ComfyUI's models folder (Windows spelling)."""
        sub = self.name.replace("/", "\\").rpartition("\\")[0]
        return "models\\" + self.folder + (("\\" + sub) if sub else "")


_HF = "https://huggingface.co/"
_BFL3 = _HF + "black-forest-labs/flux-3-image-klein-comfy/resolve/main/"
_QWEN21 = _HF + "Comfy-Org/Qwen-Image-2.1/resolve/main/"
_MOSS = _HF + "Comfy-Org/MOSS-Image/resolve/main/"
_KREA2 = _HF + "Comfy-Org/Krea-2/resolve/main/"
_SEEDVR2 = _HF + "Comfy-Org/SeedVR2/resolve/main/"
_GATED_BFL = "gated: Hugging Face login and accepting the FLUX Kommunity License"
_NC = "non-commercial use only"
_LIST = [
    # diffusion models
    File("flux3-image-klein-int8-convrot.safetensors", "unet", _BFL3 + "diffusion_models/flux3-image-klein-int8-convrot.safetensors",
         _GATED_BFL, size=5827874779),
    File("flux-2-klein-9b_int8_convrot.safetensors", "unet",
         _HF + "obsxrver/ComfyUI-Native-INT8_ConvRot/resolve/main/diffusion_models/flux-2-klein-9b_int8_convrot.safetensors",
         "licence: FLUX non-commercial (" + _NC + "); obsxrver's int8 build, A/B-tested against the old Sakujo file (2026-10-27)",
         size=9439894544),
    File("qwen_image_2.1_int8_convrot.safetensors", "unet", _QWEN21 + "diffusion_models/qwen_image_2.1_int8_convrot.safetensors",
         "licence: Qwen research licence", size=7256783064),
    File("fibo2_edit_turbo_int8_convrot.safetensors", "unet",
         _HF + "Comfy-Org/Fibo-2.0/resolve/main/diffusion_models/fibo2_edit_turbo_int8_convrot.safetensors",
         "licence: CC BY-NC 4.0 (" + _NC + ")", size=8408562474),
    File("krea2_turbo_int8_convrot.safetensors", "unet", _KREA2 + "diffusion_models/krea2_turbo_int8_convrot.safetensors",
         "licence: Krea 2 Community License", size=13492686496),
    File("moss_image_sft_int8_convrot.safetensors", "unet", _MOSS + "diffusion_models/moss_image_sft_int8_convrot.safetensors",
         "licence: Apache 2.0", size=5413698958),
    File("seedvr2_3b_int8_convrot.safetensors", "unet", _SEEDVR2 + "diffusion_models/seedvr2_3b_int8_convrot.safetensors",
         "licence: Apache 2.0", size=3458259704),
    # text encoders
    File("qwen_3_8b_fp8mixed.safetensors", "clip",
         _HF + "Comfy-Org/Flux-2-Klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
         "repo licence: FLUX non-commercial", size=8664848742),
    File("qwen3vl_4b_int8_convrot.safetensors", "clip", _KREA2 + "text_encoders/qwen3vl_4b_int8_convrot.safetensors",
         "also in Comfy-Org/Fibo-2.0 and the FLUX.3 Klein repo", size=4858559240),
    File("qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors", "clip",
         _BFL3 + "text_encoders/qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors", _GATED_BFL, size=6724090780),
    File("qwen3vl_8b_int8_convrot.safetensors", "clip", _QWEN21 + "text_encoders/qwen3vl_8b_int8_convrot.safetensors",
         "licence: Apache 2.0 (also in Comfy-Org/Qwen3-VL)", size=9350798360),
    File("qwen3.5_9b_w4a8_gptq.safetensors", "clip", _MOSS + "text_encoders/qwen3.5_9b_w4a8_gptq.safetensors",
         "licence: Apache 2.0", size=7343591088),
    File("qwen3.5_9b_int8_convrot.safetensors", "clip", _MOSS + "text_encoders/qwen3.5_9b_int8_convrot.safetensors",
         "licence: Apache 2.0", size=9748121532),
    File("qwen3vl_4b_fp8_scaled.safetensors", "clip", _KREA2 + "text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
         "licence: Apache 2.0 (also in Comfy-Org/Qwen3-VL)", size=5242467968),
    # VAEs
    File("flux2-vae.safetensors", "vae", _HF + "Comfy-Org/Flux-2-Dev/resolve/main/split_files/vae/flux2-vae.safetensors",
         "the copies in the Klein, MOSS and Fibo repos differ by a few bytes (file header) and work too", size=336213556),
    File("flux2-vae_small.safetensors", "vae", _MOSS + "vae/flux2-vae_small.safetensors", "licence: Apache 2.0", size=249521340),
    File("qwen_image_2.1_vae_bf16.safetensors", "vae", _QWEN21 + "vae/qwen_image_2.1_vae_bf16.safetensors",
         "licence: Qwen research licence", size=675509688),
    File("qwen_image_vae.safetensors", "vae", _KREA2 + "vae/qwen_image_vae.safetensors",
         "also in Comfy-Org/Qwen-Image", size=253806246),
    File("seedvr2_ema_vae_fp16.safetensors", "vae", _SEEDVR2 + "vae/seedvr2_ema_vae_fp16.safetensors",
         "licence: Apache 2.0", aliases=("ema_vae_fp16.safetensors",), size=501324814),
    # LoRAs
    File("qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors", "lora",
         _QWEN21 + "loras/qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors", "licence: Qwen research licence", size=913314512),
    File("Flux 2\\ultra_real_v4.safetensors", "lora", "https://civitai.com/api/download/models/2846977",
         "Civitai 'UltraReal - Moss, Krea2, Klein9b' by vizsumit, version KL9_V4 (Civitai may ask to log in)", size=165705592),
    File("Flux 3\\flux-3-image-klein-restore.safetensors", "lora",
         _HF + "ausboss/FLUX-3-Image-Klein-Restore-LoRA/resolve/main/flux-3-image-klein-restore.safetensors",
         "Flux 3 Upscale: ausboss' restore LoRA (on at 0.5), FLUX Kommunity License", size=160697064),
    File("Flux 3\\flux-3-image-klein-outpaint.safetensors", "lora",
         _HF + "ausboss/FLUX-3-Image-Klein-Outpaint-LoRA/resolve/main/flux-3-image-klein-outpaint.safetensors",
         "Flux 3 Expand: ausboss' outpaint LoRA, FLUX Kommunity License", size=160697104),
    File("Moss\\lora_dmd2.safetensors", "lora", _HF + "lodestones/MOSS-Image-Base-8-steps-dmd/resolve/main/lora_dmd2.safetensors",
         "licence: Apache 2.0", size=1189176800),
    File("Moss\\lenovo_moss.safetensors", "lora", _HF + "Danrisi/lenovo_moss/resolve/main/lenovo_moss.safetensors",
         "Lenovo UltraReal by Danrisi (also on Civitai, model 1662740)", size=64527960),
]
_LIST += [
    # the reference slots' "Cut out" button (ComfyUI's own BiRefNet nodes)
    File("birefnet.safetensors", "bg_removal", _HF + "Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors",
         "optional: \"Cut out\" in the reference slots; licence: MIT", size=444473596),
]
_TAESD = "https://raw.githubusercontent.com/madebyollin/taesd/main/"      # not github.com: its certificate chain fails in Windows Python
_LIVE = "optional: sharper live preview (without it ComfyUI shows coarse colours); "
_LIST += [
    # live preview decoders (T3a, user 29.10.: optional, linked here; whether they are better is tested live)
    File("taef2_decoder.pth", "preview", _TAESD + "taef2_decoder.pth", _LIVE + "licence: MIT (madebyollin/taesd)",
         aliases=("taef2_decoder.safetensors",), size=2704756),
    File("taeqi2_1_decoder.pth", "preview", _TAESD + "taeqi2_1_decoder.pth", _LIVE + "licence: MIT (madebyollin/taesd)",
         aliases=("taeqi2_1_decoder.safetensors",), size=15314938),
    File("lighttaew2_1.safetensors", "preview", _HF + "lightx2v/Autoencoders/resolve/main/lighttaew2_1.safetensors",
         _LIVE + "licence: Apache 2.0 (lightx2v/Autoencoders)", aliases=("lighttaew2_1.pth",), size=45274004),
]
# SHA-256 as Hugging Face (LFS) and Civitai publish them, read from their APIs on 2026-10-30 without downloading; the
# sizes above matched too. The TAESD decoders on GitHub have none published (the download checks their size only).
_SHA256 = {
    'flux3-image-klein-int8-convrot.safetensors': "847d8933548afd93df4af2cac2498e70891bf28d9dae06d695f536992e168fe2",
    'flux-2-klein-9b_int8_convrot.safetensors': "bd041cec0d7955d6fcbaef952ba6ebe37af9f7d032ec927657e7777f21f5c522",
    'qwen_image_2.1_int8_convrot.safetensors': "cb74113cb03faecd79611b01fd7fd642f0aa60d6f0b95086abee214d75eaa57d",
    'fibo2_edit_turbo_int8_convrot.safetensors': "1f6fa7c499191f405467123f655f11762661eaa5bd479d1da8f161398ef72c3b",
    'krea2_turbo_int8_convrot.safetensors': "8e4eeda70dd5037ab1ba2bef6b417f9f901e26093117cf397f741fc1fdaaf3f1",
    'moss_image_sft_int8_convrot.safetensors': "b4d1475bc7eeffd7b809e82ea13a1fba1fb85c4e18365af3813722faa5c0fe4f",
    'seedvr2_3b_int8_convrot.safetensors': "c3dec8bcc5916843a8a858572970597462e1f2dc598d6dfd818f6cd40f53a157",
    'qwen_3_8b_fp8mixed.safetensors': "abad16806e0cbabc54e0325d6565847443fe396d5f0be38bb3cd3fe75a1201d6",
    'qwen3vl_4b_int8_convrot.safetensors': "32de113cbf8282b02cbff0794b637b9d6676da09314a1db5a30bcea9bf4ee01c",
    'qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors': "e5d85a7421d197bf5a12474511936ecabce19a833252f16e9310a983194a4458",
    'qwen3vl_8b_int8_convrot.safetensors': "8bfd0f6e12abf2d2d697ecc888e5e90b0d6741d6708f05799f53afa560452e8f",
    'qwen3.5_9b_w4a8_gptq.safetensors': "4cc6a1543ad2061806da46f35f90cadb4801dcba246c44782cf42ec0feb6407c",
    'qwen3.5_9b_int8_convrot.safetensors': "32e3787472f708fa5f83624acbf5ef23f7fc89c439e05065ea57cfe5a97f025a",
    'qwen3vl_4b_fp8_scaled.safetensors': "54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094",
    'flux2-vae.safetensors': "d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5",
    'flux2-vae_small.safetensors': "d8d52ba036475f5fb07c8b435e176d3d97ebfa82f0d1a1c317f9cc1e25bd013b",
    'qwen_image_2.1_vae_bf16.safetensors': "bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9",
    'qwen_image_vae.safetensors': "a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f",
    'seedvr2_ema_vae_fp16.safetensors': "20678548f420d98d26f11442d3528f8b8c94e57ee046ef93dbb7633da8612ca1",
    'qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors': "208dd43250e1e01467ba190572ae2e7107a7870ec1ff026bc65f791fa1e80e95",
    'Flux 2\\ultra_real_v4.safetensors': "df2307852d99e103917e6bc60e58da8971769bf716dee443f10b201fcee6ca18",
    'Flux 3\\flux-3-image-klein-restore.safetensors': "7b758f5c1d494da7675dbebd8309f36c3dcaf4aa67a3349f667403c7a681187e",
    'Flux 3\\flux-3-image-klein-outpaint.safetensors': "25385da7f6bfac0c18513e52729dc29f96cda543f0d086df9e5dda3842dede83",
    'Moss\\lora_dmd2.safetensors': "7683fe1fb51f73f5d690f24dd6b7f46f31ab9a9873729a854ac5c9a420ffe6f2",
    'Moss\\lenovo_moss.safetensors': "f28ab12e33e60146c8740a86730385cf5ba488e9f6eda50b14383d6ddbf300fb",
    'birefnet.safetensors': "9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154",
    'lighttaew2_1.safetensors': "8666e769f449f2d955651564bcadb0c5e12461b50480e67b7241f32c15f11a19",
}
_LIST = [replace(f, sha256=_SHA256.get(f.name, "")) for f in _LIST]
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
_TAEF2 = "taef2_decoder.pth"            # live preview of the Flux 2 latent: Flux 2, Flux 3, Fibo, MOSS
_CUT = ModeSpec(optional=("birefnet.safetensors",))     # Multi Image Edit: "Cut out" in the reference slots

TABS: dict[str, TabSpec] = {
    "flux3": TabSpec(
        required=("flux3-image-klein-int8-convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", _UPS),
        modes={
            "txt2img": ModeSpec(optional=(_UPSAMPLER,)),
            "outpaint": ModeSpec(requires=("Flux 3\\flux-3-image-klein-outpaint.safetensors",)),
            "upscale": ModeSpec(requires=("seedvr2_3b_int8_convrot.safetensors", "seedvr2_ema_vae_fp16.safetensors",
                                          "Flux 3\\flux-3-image-klein-restore.safetensors"),
                                nodes=_FLUX3_UP_NODES),
            "multi_edit": _CUT,
        },
        optional=(_TAEF2,)),
    "flux2": TabSpec(
        required=("flux-2-klein-9b_int8_convrot.safetensors", "qwen_3_8b_fp8mixed.safetensors", _UPS),
        modes={
            "txt2img": ModeSpec(optional=(_UPSAMPLER,)),
            "upscale": ModeSpec(requires=_ULTRA),
            "refine": ModeSpec(requires=_ULTRA),
            "multi_edit": _CUT,
        },
        optional=(_TAEF2,)),
    "qwen": TabSpec(
        required=("qwen_image_2.1_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"),
        modes={
            "txt2img": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",), optional=("qwen3.5_9b_w4a8_gptq.safetensors",)),
            "edit": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "inpaint": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "outpaint": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "multi_edit": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",), optional=_CUT.optional),   # runs the edit graph
            "remove": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
        },
        optional=("qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors", "taeqi2_1_decoder.pth")),
    "fibo": TabSpec(
        required=("fibo2_edit_turbo_int8_convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", _UPS),
        modes={"multi_edit": _CUT},
        optional=("qwen3.5_9b_int8_convrot.safetensors", _TAEF2)),      # the prompt writer (LLM prompt enhancement)
    "krea2": TabSpec(
        required=("krea2_turbo_int8_convrot.safetensors", "qwen3vl_4b_fp8_scaled.safetensors", "qwen_image_vae.safetensors"),
        optional=("lighttaew2_1.safetensors",)),          # live preview of the Wan 2.1 latent
    "moss": TabSpec(
        required=("moss_image_sft_int8_convrot.safetensors", "qwen3.5_9b_w4a8_gptq.safetensors", "flux2-vae_small.safetensors"),
        # Text to image starts with the UltraReal LoRA on: a file the start values use is required (user 30.10.)
        modes={"txt2img": ModeSpec(requires=("Moss\\lenovo_moss.safetensors",))},
        optional=("Moss\\lora_dmd2.safetensors", _TAEF2)),
}


def used_by(name: str) -> list[str]:
    """The models (keys, in the order of TABS) whose list names this file, as a required or optional one."""
    out = []
    for key, t in TABS.items():
        names = set(t.required) | set(t.optional)
        for ms in t.modes.values():
            names |= set(ms.requires) | set(ms.optional)
        if name in names:
            out.append(key)
    return out


def preview_decoder(key: str) -> str:
    """The live preview decoder (TAESD) of a model: "" when it has none."""
    t = TABS.get(key)
    return next((n for n in (t.optional if t else ()) if n in FILES and FILES[n].kind == "preview"), "")


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
