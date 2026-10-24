"""ComfyUI graphs in API format.

1) Built-in – work with any SD1.5/SDXL checkpoint (core ComfyUI nodes only):
   txt2img, img2img, inpaint (InpaintModelConditioning + DifferentialDiffusion).

2) Custom – a JSON file exported from ComfyUI with "Export (API)". The bridge fills in values
   on nodes whose TITLE starts with "pc:" (right-click a node → Title):

     pc:image     LoadImage              ← the image crop from PhotoCraft
     pc:mask      LoadImage              ← the mask (white = generate); follow with e.g. ImageToMask
     pc:prompt    node with a `text` field ← prompt
     pc:negative  node with a `text` field ← negative prompt
     pc:sampler   KSampler/RandomNoise/… ← seed / noise_seed, denoise (whichever it has)
     pc:latent    EmptyLatentImage/…     ← width, height, batch_size
     pc:size      anything with width/height ← width, height
     pc:output    SaveImage/PreviewImage ← the result is taken from here (else: first node with images)

   Model, steps, CFG and sampler stay as saved in the workflow – it is the "recipe" for that model
   (Flux wants CFG 1 and FluxGuidance 30, SDXL something else entirely).

   That way Flux Fill, Qwen-Image-Edit, ControlNet etc. plug in without code changes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenParams:
    prompt: str = ""
    negative: str = ""
    checkpoint: str = ""
    steps: int = 25
    cfg: float = 6.0
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    seed: int = -1
    denoise: float = 1.0
    clip: str = ""            # text model for nodes tagged pc:clip (e.g. the VGL writer); empty = the workflow's own
    width: int = 1024
    height: int = 1024
    batch: int = 1
    differential_diffusion: bool = True
    extra: dict = field(default_factory=dict)


# ---------- wbudowane ----------

def _base(p: GenParams) -> dict:
    return {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": p.checkpoint},
                 "_meta": {"title": "pc:model"}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": p.prompt, "clip": ["ckpt", 1]}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": p.negative, "clip": ["ckpt", 1]}},
        "sampler": {"class_type": "KSampler", "inputs": {
            "seed": p.seed, "steps": p.steps, "cfg": p.cfg, "sampler_name": p.sampler,
            "scheduler": p.scheduler, "denoise": p.denoise,
            "model": ["ckpt", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": None}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["ckpt", 2]}},
        "out": {"class_type": "PreviewImage", "inputs": {"images": ["decode", 0]}, "_meta": {"title": "pc:output"}},
    }


def txt2img(p: GenParams) -> dict:
    g = _base(p)
    g["latent"] = {"class_type": "EmptyLatentImage", "inputs": {"width": p.width, "height": p.height, "batch_size": p.batch}}
    g["sampler"]["inputs"]["latent_image"] = ["latent", 0]
    g["sampler"]["inputs"]["denoise"] = 1.0
    return g


def img2img(p: GenParams, image_name: str) -> dict:
    g = _base(p)
    g["load"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["encode"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["load", 0], "vae": ["ckpt", 2]}}
    g["batch"] = {"class_type": "RepeatLatentBatch", "inputs": {"samples": ["encode", 0], "amount": p.batch}}
    g["sampler"]["inputs"]["latent_image"] = ["batch", 0]
    return g


def inpaint(p: GenParams, image_name: str, mask_name: str) -> dict:
    g = _base(p)
    g["load"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    g["load_mask"] = {"class_type": "LoadImage", "inputs": {"image": mask_name}}
    g["mask"] = {"class_type": "ImageToMask", "inputs": {"image": ["load_mask", 0], "channel": "red"}}
    g["cond"] = {"class_type": "InpaintModelConditioning", "inputs": {
        "positive": ["pos", 0], "negative": ["neg", 0], "vae": ["ckpt", 2],
        "pixels": ["load", 0], "mask": ["mask", 0], "noise_mask": True}}
    g["batch"] = {"class_type": "RepeatLatentBatch", "inputs": {"samples": ["cond", 2], "amount": p.batch}}
    s = g["sampler"]["inputs"]
    s.update(positive=["cond", 0], negative=["cond", 1], latent_image=["batch", 0])
    if p.differential_diffusion:
        # soft mask edges = gradual denoising (better blending)
        g["diff"] = {"class_type": "DifferentialDiffusion", "inputs": {"model": ["ckpt", 0]}}
        s["model"] = ["diff", 0]
    return g


def inpaint_fooocus(p: GenParams, image_name: str, mask_name: str, head: str, patch: str,
                    fill: str = "neutral") -> dict:
    """Inpaint like Krita AI Diffusion (SDXL): the Fooocus patch turns a regular SDXL checkpoint into an inpaint model.

    Needs comfyui-inpaint-nodes (the Krita plugin installs them) and the files in models/inpaint.
    At full denoise the masked area is pre-filled first: grey ("neutral", new object) or blurred
    surrounding colours ("blur", outpaint), so old content doesn't bleed through and there are no seams.
    """
    g = _base(p)
    g["load"] = {"class_type": "LoadImage", "inputs": {"image": image_name}, "_meta": {"title": "pc:image"}}
    g["load_mask"] = {"class_type": "LoadImage", "inputs": {"image": mask_name}, "_meta": {"title": "pc:mask"}}
    g["mask"] = {"class_type": "ImageToMask", "inputs": {"image": ["load_mask", 0], "channel": "red"}}
    pixels = ["load", 0]
    if p.denoise >= 0.99 and fill != "none":
        if fill == "neutral":  # grey: the model draws new content, old content doesn't bleed through
            g["prefill"] = {"class_type": "INPAINT_MaskedFill", "inputs": {
                "image": pixels, "mask": ["mask", 0], "fill": "neutral", "falloff": 0}}
            pixels = ["prefill", 0]
        # "blur": blurred surroundings (outpaint – the area is already pre-filled by the bridge)
        g["preblur"] = {"class_type": "INPAINT_MaskedBlur", "inputs": {
            "image": pixels, "mask": ["mask", 0], "blur": 65, "falloff": 9}}
        pixels = ["preblur", 0]
    g["cond"] = {"class_type": "INPAINT_VAEEncodeInpaintConditioning", "inputs": {
        "positive": ["pos", 0], "negative": ["neg", 0], "vae": ["ckpt", 2], "pixels": pixels, "mask": ["mask", 0]}}
    g["fooocus_load"] = {"class_type": "INPAINT_LoadFooocusInpaint", "inputs": {"head": head, "patch": patch}}
    g["fooocus_apply"] = {"class_type": "INPAINT_ApplyFooocusInpaint", "inputs": {
        "model": ["ckpt", 0], "patch": ["fooocus_load", 0], "latent": ["cond", 2]}}
    model = ["fooocus_apply", 0]
    if p.differential_diffusion:
        g["diff"] = {"class_type": "DifferentialDiffusion", "inputs": {"model": model}}
        model = ["diff", 0]
    g["batch"] = {"class_type": "RepeatLatentBatch", "inputs": {"samples": ["cond", 3], "amount": p.batch}}
    g["sampler"]["inputs"].update(model=model, positive=["cond", 0], negative=["cond", 1], latent_image=["batch", 0])
    g["pos"]["_meta"] = {"title": "pc:prompt"}
    g["neg"]["_meta"] = {"title": "pc:negative"}
    g["sampler"]["_meta"] = {"title": "pc:sampler"}
    return g


# ---------- custom (templates) ----------

def load_template(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "nodes" in data and "links" in data:
        raise ValueError(f"{Path(path).name}: this is a UI-format save. In ComfyUI use Workflow → Export (API).")
    if not all(isinstance(v, dict) and "class_type" in v for v in data.values()):
        raise ValueError(f"{Path(path).name}: this doesn't look like an API-format workflow.")
    return data


def resolve(path: str | Path) -> list[str]:
    """A normal workflow is itself; a `*.group.json` ({"workflows": [...]}) expands to several, run one after another."""
    p = Path(path)
    if p.name.lower().endswith(".group.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        names = data.get("workflows") if isinstance(data, dict) else None
        if not names:
            raise ValueError(f"{p.name}: a group file needs a non-empty \"workflows\" list.")
        return [str(p.parent / n) for n in names]
    return [str(p)]


def apply_template(graph: dict, p: GenParams, image_name: str | None, mask_name: str | None) -> tuple[dict, str | None]:
    """Fill parameters into `pc:*` nodes. Returns (graph, output node id or None).

    A title may carry several tags (e.g. "pc:prompt pc:size" for one node that takes the prompt and the size).
    `pc:prompt` fills the node's `text` field, else its `instruction` field (VGLBionicEditPrompt), else its `prompt` field
    (TextGenerate, TextEncodeFibo2, ...).
    """
    g = json.loads(json.dumps(graph))  # deep copy
    out_node = None
    seen = set()
    for nid, node in g.items():
        title = node.get("_meta", {}).get("title", "").strip().lower()
        tags = re.findall(r"pc:\s*([a-z]+)", title)
        if not tags:
            continue
        inp = node.setdefault("inputs", {})
        for tag in tags:
            seen.add(tag)
            if tag == "image":
                if image_name is None:
                    raise ValueError("The workflow has a pc:image node, but this mode sends no image.")
                inp["image"] = image_name
            elif tag == "mask":
                if mask_name is None:
                    raise ValueError("The workflow has a pc:mask node, but this mode has no mask (selection).")
                inp["image"] = mask_name
            elif tag == "prompt":
                key = next((k for k in ("text", "instruction", "prompt") if k in inp), "prompt")
                inp[key] = p.prompt
            elif tag == "negative":
                key = "text" if "text" in inp else "negative_prompt"
                inp[key] = p.negative
            elif tag == "sampler":
                for k, v in (("seed", p.seed), ("noise_seed", p.seed), ("denoise", p.denoise)):
                    if k in inp and not isinstance(inp[k], list):
                        inp[k] = v
            elif tag in ("latent", "size"):
                for k, v in (("width", p.width), ("height", p.height), ("batch_size", p.batch)):
                    if k in inp and not isinstance(inp[k], list):
                        inp[k] = v
            elif tag == "clip":
                if p.clip and "clip_name" in inp:
                    inp["clip_name"] = p.clip
            elif tag == "output":
                out_node = nid
    if image_name is not None and "image" not in seen:
        raise ValueError("The workflow has no LoadImage node titled pc:image.")
    if mask_name is not None and "mask" not in seen:
        raise ValueError("The workflow has no mask node titled pc:mask.")
    return g, out_node


TEXT_ENCODERS = ("TextEncode", "CLIPTextEncode")


def _tags(node: dict) -> list[str]:
    return re.findall(r"pc:\s*([a-z]+)", node.get("_meta", {}).get("title", "").lower())


def prompt_writers(graph: dict) -> list[str]:
    """Ids of the text-model nodes that write the prompt: pc:prompt nodes that are not a plain text encoder."""
    return [nid for nid, n in graph.items()
            if "prompt" in _tags(n) and not n.get("class_type", "").startswith(TEXT_ENCODERS)]


def bypass_prompt_writer(graph: dict, prompt: str) -> dict:
    """Prompt enhancement off: whatever consumed the text model's output gets the typed prompt itself.

    The text model, the pc:vgl preview and (because ComfyUI only runs what an output needs) everything that only fed
    the text model drop out of the run. Graphs without a text model are returned unchanged.
    """
    g = json.loads(json.dumps(graph))
    writers = {str(w) for w in prompt_writers(g)}
    if not writers:
        return g

    def uses_writer(node):
        return any(isinstance(v, list) and v and str(v[0]) in writers for v in node.get("inputs", {}).values())

    for nid in [nid for nid, n in g.items() if "vgl" in _tags(n) and uses_writer(n)]:
        del g[nid]
    for n in g.values():
        inp = n.get("inputs", {})
        for k, v in inp.items():
            if isinstance(v, list) and v and str(v[0]) in writers:
                inp[k] = prompt
    for w in writers:
        g.pop(w, None)
    return g


def list_templates(folder: str | Path) -> list[Path]:
    folder = Path(folder).expanduser()
    return sorted(folder.glob("*.json")) if folder.is_dir() else []
