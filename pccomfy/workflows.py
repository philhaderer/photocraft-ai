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
     pc:upscale   node with a `megapixels` field ← size of the result (Upscale and Refine modes: the bridge computes it
                  from the picture and the factor; the picture itself goes to the workflow at its own size)

   Model, steps, CFG and sampler stay as saved in the workflow – it is the "recipe" for that model
   (Flux wants CFG 1 and FluxGuidance 30, SDXL something else entirely).

   That way Flux Fill, Qwen-Image-Edit, ControlNet etc. plug in without code changes.

   Two optional fields in a node's `_meta` (next to the title) let a workflow describe its model:
     pc_default_prompt  on the pc:prompt node: the prompt that is used when nothing is typed (Upscale / Refine).
     pc_image_tag   on the pc:prompt node: how the model names the picture in its prompt ("<image1>" for Qwen Image 2.1,
                    "<ref_image_0>" for FLUX.3 Klein). The bridge puts it in front of the typed text.
     pc:lora        (a title tag) on a speed/turbo LoRA loader the window can switch off; the pc:sampler node's
                    `pc_no_lora` ({"steps": 25}) says what the sampler needs without it.
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


def apply_template(graph: dict, p: GenParams, image_name: str | None, mask_name: str | None,
                   ref_name: str | None = None, ref_first: bool = True) -> tuple[dict, str | None]:
    """Fill parameters into `pc:*` nodes. Returns (graph, output node id or None).

    A title may carry several tags (e.g. "pc:prompt pc:size" for one node that takes the prompt and the size).
    `pc:prompt` fills the node's `text` field, else its `instruction` field (VGLBionicEditPrompt), else its `prompt` field
    (TextGenerate, TextEncodeFibo2, ...).
    `pc:ref` is the slot for a reference image (a LoadImage feeding TextEncodeFibo2's `images.image_2`). The slot is
    always in the workflow; with no reference (`ref_name` None) the node and the links to it are dropped, so the run
    is exactly the one-image run. With a reference it becomes `image_1` and the picture `image_2` (reference_first).
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
                if image_name is not None:
                    inp["image"] = image_name
            elif tag == "mask":
                if mask_name is not None:
                    inp["image"] = mask_name
            elif tag == "prompt":
                key = next((k for k in ("text", "instruction", "prompt") if k in inp), "prompt")
                inp[key] = with_image_tag(p.prompt.strip() and p.prompt or default_prompt(node) or p.prompt, node)
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
            elif tag == "upscale":
                if "megapixels" in p.extra and "megapixels" in inp and not isinstance(inp["megapixels"], list):
                    inp["megapixels"] = round(float(p.extra["megapixels"]), 4)
            elif tag == "output":
                out_node = nid
            elif tag == "ref" and ref_name is not None:
                inp["image"] = ref_name
    if image_name is not None and "image" not in seen:
        raise ValueError("The workflow has no LoadImage node titled pc:image.")
    if mask_name is not None and "mask" not in seen:
        raise ValueError("The workflow has no mask node titled pc:mask.")
    if ref_name is not None and "ref" not in seen:
        raise ValueError("The workflow has no reference slot (a LoadImage node titled pc:ref).")
    if image_name is None and "image" in seen and not drop_empty_slot(g, "image", only_keys="images."):
        raise ValueError("The workflow has a pc:image node, but this mode sends no image.")
    if mask_name is None and "mask" in seen and not drop_empty_slot(g, "mask"):
        raise ValueError("The workflow has a pc:mask node, but this mode has no mask (selection).")
    if ref_name is None:
        drop_ref_slot(g)
    elif ref_first:
        reference_first(g)
    return g, out_node


def has_upscale_slot(graph: dict) -> bool:
    """True when the workflow can enlarge or refine a picture (a node titled pc:upscale sets the result's size)."""
    return any("upscale" in _tags(n) for n in graph.values() if isinstance(n, dict))


def default_prompt(node: dict) -> str:
    """What a pc:prompt node asks for when nothing is typed: the `pc_default_prompt` field in its _meta (the Flux 2
    Klein upscale: a description of a clean photo). Empty = the workflow has none."""
    return str(node.get("_meta", {}).get("pc_default_prompt", "")).strip()


def image_tag(node: dict) -> str:
    """How the model names the picture in its prompt ("<image1>", "<ref_image_0>"): the `pc_image_tag` field in the
    _meta of the pc:prompt node. Empty = the model needs none (Fibo)."""
    return str(node.get("_meta", {}).get("pc_image_tag", "")).strip()


def with_image_tag(prompt: str, node: dict) -> str:
    """The prompt with the picture's tag in front. Left alone when the workflow names no tag, when there is no text,
    or when the text already mentions the tag (typed by hand)."""
    tag, text = image_tag(node), prompt.strip()
    if not tag or not text or tag.lower() in text.lower():
        return prompt
    return f"{tag} {text}"


def has_ref_slot(graph: dict) -> bool:
    """True when the workflow has a reference-image slot (a node titled pc:ref)."""
    return any("ref" in _tags(n) for n in graph.values() if isinstance(n, dict))


def reference_first(graph: dict) -> None:
    """Fibo 2 Edit composes best with the subject first and the scene second ("Place the subject from <image_1> into
    <image_2>", Bria's own example): with the scene first the model redraws the reference as the result and ignores
    the scene. A node that takes both the picture (pc:image) and the reference (pc:ref) gets them swapped."""
    pic = {nid for nid, n in graph.items() if "image" in _tags(n)}
    ref = {nid for nid, n in graph.items() if "ref" in _tags(n)}
    for n in graph.values():
        inp = n.get("inputs", {})
        a = [k for k, v in inp.items() if isinstance(v, list) and v and str(v[0]) in pic]
        b = [k for k, v in inp.items() if isinstance(v, list) and v and str(v[0]) in ref]
        if len(a) == 1 and len(b) == 1:
            inp[a[0]], inp[b[0]] = inp[b[0]], inp[a[0]]


def drop_empty_slot(graph: dict, tag: str, only_keys: str = "") -> bool:
    """A slot (pc:image / pc:mask) this mode cannot fill: remove its nodes and the inputs linked to them, but only when
    that is harmless: nothing links to the mask at all (Fibo loads it and ignores it), and the picture is only linked
    into optional inputs starting with `only_keys` (Fibo's `images.image_N`, which may stay empty). False = untouched."""
    ids = {nid for nid, n in graph.items() if tag in _tags(n)}
    uses = [(nid, k) for nid, n in graph.items() if nid not in ids
            for k, v in n.get("inputs", {}).items() if isinstance(v, list) and v and str(v[0]) in ids]
    if any(not (only_keys and k.startswith(only_keys)) for _, k in uses):
        return False
    for nid in ids:
        del graph[nid]
    for nid, k in uses:
        del graph[nid]["inputs"][k]
    return True


def drop_ref_slot(graph: dict) -> None:
    """No reference image: remove the pc:ref nodes and every input that was linked to them (in place)."""
    ids = {nid for nid, n in graph.items() if "ref" in _tags(n)}
    for nid in ids:
        del graph[nid]
    for n in graph.values():
        inp = n.get("inputs", {})
        for k in [k for k, v in inp.items() if isinstance(v, list) and v and str(v[0]) in ids]:
            del inp[k]


TEXT_ENCODERS = ("TextEncode", "CLIPTextEncode", "AUSBOSS_NODES_Text")   # plain text holders: not a text model


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


def lora_switches(graph: dict) -> list[str]:
    """Ids of the nodes titled pc:lora: speed (turbo) LoRAs the window can switch off."""
    return [nid for nid, n in graph.items() if isinstance(n, dict) and "lora" in _tags(n)]


def bypass_lora(graph: dict) -> dict:
    """Turbo LoRA off: the pc:lora loaders drop out of the graph (whatever read their model gets the model they were
    given) and every pc:sampler takes the values its `pc_no_lora` field lists (e.g. 25 steps instead of 10).
    Graphs without a pc:lora node are returned unchanged."""
    g = json.loads(json.dumps(graph))
    loras = {str(i) for i in lora_switches(g)}
    if not loras:
        return g

    def source(nid: str):
        link = g[nid].get("inputs", {}).get("model")
        while isinstance(link, list) and link and str(link[0]) in loras:   # two LoRAs in a row
            link = g[str(link[0])].get("inputs", {}).get("model")
        return link

    for n in g.values():
        for k, v in n.get("inputs", {}).items():
            if isinstance(v, list) and v and str(v[0]) in loras:
                n["inputs"][k] = source(str(v[0]))
    for nid in loras:
        del g[nid]
    for n in g.values():
        if "sampler" in _tags(n):
            inp = n.get("inputs", {})
            for k, v in (n.get("_meta", {}).get("pc_no_lora") or {}).items():
                if k in inp and not isinstance(inp[k], list):
                    inp[k] = v
    return g


def list_templates(folder: str | Path) -> list[Path]:
    folder = Path(folder).expanduser()
    return sorted(folder.glob("*.json")) if folder.is_dir() else []
