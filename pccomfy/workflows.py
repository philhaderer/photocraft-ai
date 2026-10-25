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
                for k, v in (("width", p.width), ("height", p.height), ("batch_size", p.batch), ("amount", p.batch)):
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


def size_multiple(graph: dict) -> int:
    """The multiple the picture sent to the model must be a multiple of: `pc_size_multiple` in the _meta of a node
    (Qwen Image 2.1 keeps reference images at multiples of 32; any other size shifts the edit). Default 16."""
    vals = [int(n.get("_meta", {}).get("pc_size_multiple", 0) or 0) for n in graph.values() if isinstance(n, dict)]
    return max([16] + vals)


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


SAMPLING_NODES = ("KSampler", "KSamplerAdvanced", "CFGGuider", "DualCFGGuider", "SamplerCustom", "BasicGuider")


def _model_root(g: dict, link) -> str:
    """Title of the loader a model link starts from (follows LoRA / patch nodes upstream)."""
    seen = 0
    while isinstance(link, list) and link and str(link[0]) in g and seen < 40:
        node = g[str(link[0])]
        nxt = node.get("inputs", {}).get("model")
        if not isinstance(nxt, list):
            return str(node.get("_meta", {}).get("title", ""))
        link, seen = nxt, seen + 1
    return ""


def add_loras(graph: dict, loras: list) -> dict:
    """Extra LoRAs the user picked: [(file name, strength), ...] are chained in front of every sampler / guider that
    takes a model - except one fed by a helper model (a loader titled SeedVR2). A copy is returned."""
    g = json.loads(json.dumps(graph))
    loras = [(str(n), float(st)) for n, st in loras or [] if n]
    if not loras:
        return g
    sinks = [(nid, n) for nid, n in g.items() if isinstance(n, dict) and n.get("class_type") in SAMPLING_NODES
             and isinstance(n.get("inputs", {}).get("model"), list) and "seedvr" not in _model_root(g, n["inputs"]["model"]).lower()]
    made: dict[tuple, list] = {}
    for nid, n in sinks:
        src = n["inputs"]["model"]
        key = (str(src[0]), src[1])
        if key not in made:
            link = list(src)
            for i, (name, st) in enumerate(loras):
                new = f"pcx{len(g)}_{i}"
                while new in g:
                    new += "_"
                g[new] = {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": name, "strength_model": round(st, 3), "model": link},
                          "_meta": {"title": f"Extra LoRA {name}"}}
                link = [new, 0]
            made[key] = link
        n["inputs"]["model"] = made[key]
    return g


def writer_model(graph: dict) -> str:
    """Which text model writes the prompt: `pc_llm_tip` of the writer node, else the file name of the text model it reads
    (the clip loader it is wired to, or a model name set on the node itself). "" = no text model in the workflow."""
    for nid in prompt_writers(graph):
        node = graph[nid]
        tip = str(node.get("_meta", {}).get("pc_llm_tip", "")).strip()
        if tip:
            return tip
        inp = node.get("inputs", {})
        link = inp.get("clip")
        if isinstance(link, list) and link and str(link[0]) in graph:
            name = graph[str(link[0])].get("inputs", {}).get("clip_name")
            if isinstance(name, str):
                return name
        for k in ("model", "model_name", "clip_name", "llm"):
            if isinstance(inp.get(k), str):
                return inp[k]
    return ""


def writer_name(graph: dict) -> str:
    """The short name of the text model that writes the prompt, for the checkbox ("LLM prompt enhancement (Qwen 3.5 9B)"):
    `pc_llm_name` of the writer node, else the model's file name without its extension. "" = no text model."""
    for nid in prompt_writers(graph):
        name = str(graph[nid].get("_meta", {}).get("pc_llm_name", "")).strip()
        if name:
            return name
    raw = writer_model(graph)
    if not raw or " " in raw.strip():     # a sentence (pc_llm_tip) is not a name
        return ""
    return re.sub(r"\.(safetensors|gguf)$", "", raw.strip())


def main_sampler(graph: dict) -> str | None:
    """Id of the sampler that draws the picture: a KSampler / KSamplerAdvanced titled pc:sampler, else the last one that is
    not fed by a helper model (SeedVR2). None when the workflow has none (or sets its values another way)."""
    nodes = [(nid, n) for nid, n in graph.items() if isinstance(n, dict) and n.get("class_type") in ("KSampler", "KSamplerAdvanced")
             and "seedvr" not in _model_root(graph, n.get("inputs", {}).get("model")).lower()]
    tagged = [nid for nid, n in nodes if "sampler" in _tags(n) and isinstance(n.get("inputs", {}).get("steps"), (int, float))]
    if tagged:
        return tagged[-1]
    return nodes[-1][0] if nodes else None


def sampler_values(graph: dict) -> dict:
    """What the main sampler is set to: {steps, cfg, denoise, sampler, scheduler} (a key is missing when the workflow
    wires it from elsewhere). Apply `bypass_lora` first to get the values without the speed LoRA."""
    nid = main_sampler(graph)
    out = {}
    if nid is None:
        sel = _sampler_select(graph)       # Flux 2 Klein: SamplerCustomAdvanced; only the sampler is a plain value
        if sel is not None and isinstance(graph[sel].get("inputs", {}).get("sampler_name"), str):
            out["sampler"] = graph[sel]["inputs"]["sampler_name"]
        return out
    inp = graph[nid].get("inputs", {})
    for key, name in (("steps", "steps"), ("cfg", "cfg"), ("denoise", "denoise"), ("sampler", "sampler_name"), ("scheduler", "scheduler")):
        v = inp.get(name)
        if v is not None and not isinstance(v, list):
            out[key] = v
    return out


def _sampler_select(graph: dict) -> str | None:
    """Id of the KSamplerSelect node (the sampler name of a SamplerCustomAdvanced workflow), None when there is none."""
    ids = [nid for nid, n in graph.items() if isinstance(n, dict) and n.get("class_type") == "KSamplerSelect"]
    return ids[-1] if ids else None


def set_sampler(graph: dict, steps=None, cfg=None, denoise=None, sampler=None, scheduler=None) -> dict:
    """The main sampler runs with these values (None = leave as the workflow has it). A copy is returned."""
    g = json.loads(json.dumps(graph))
    nid = main_sampler(g)
    if nid is None:
        sel = _sampler_select(g)
        if sel is not None and sampler and "sampler_name" in g[sel].get("inputs", {}):
            g[sel]["inputs"]["sampler_name"] = sampler
        return g
    inp = g[nid].get("inputs", {})
    for name, v in (("sampler_name", sampler), ("scheduler", scheduler)):
        if v and name in inp and not isinstance(inp[name], list):
            inp[name] = v
    for name, v in (("steps", steps), ("cfg", cfg), ("denoise", denoise)):
        if v is not None and name in inp and not isinstance(inp[name], list):
            inp[name] = v
    return g


def lora_strength(graph: dict) -> float | None:
    """The strength the workflow's pc:lora loader is set to (LoraLoaderModelOnly, or AusBoss' LoRA list), None without one."""
    for nid in lora_switches(graph):
        inp = graph[nid].get("inputs", {})
        if isinstance(inp.get("strength_model"), (int, float, str)) and not isinstance(inp.get("strength_model"), list):
            try:
                return float(inp["strength_model"])
            except ValueError:
                pass
        if isinstance(inp.get("loras"), str):
            try:
                items = json.loads(inp["loras"])
                return float(items[0]["strength"])
            except (ValueError, KeyError, IndexError, TypeError):
                pass
    return None


def set_lora_strength(graph: dict, value: float) -> dict:
    """The pc:lora loaders run at `value` (a copy of the graph is returned)."""
    g = json.loads(json.dumps(graph))
    for nid in lora_switches(g):
        inp = g[nid].get("inputs", {})
        if "strength_model" in inp and not isinstance(inp["strength_model"], list):
            inp["strength_model"] = round(float(value), 3)
        if isinstance(inp.get("loras"), str):
            try:
                items = json.loads(inp["loras"])
                for it in items:
                    it["strength"] = round(float(value), 3)
                inp["loras"] = json.dumps(items, separators=(",", ":"))
            except (ValueError, TypeError):
                pass
    return g


def stage_switches(graph: dict) -> list[tuple[str, str]]:
    """(node id, label) of the stages the window can switch off: a node whose _meta has `pc_stage_off`
    ({"label": ..., "set": {input: link}, "remove": [node ids], "rewire": [node ids], "default_on": bool}) - e.g. the
    SeedVR2 pre-cleaning of the Flux 3 upscale, or an optional LoRA / skip-layer patch of MOSS (`rewire`: the node
    drops out and whatever read its model reads the model it was given)."""
    return [(nid, str(n["_meta"]["pc_stage_off"].get("label", "Stage"))) for nid, n in graph.items()
            if isinstance(n, dict) and isinstance(n.get("_meta", {}).get("pc_stage_off"), dict)]


def stage_info(graph: dict) -> list[dict]:
    """The switchable stages of a workflow, in order: {id, label, tip, default_on} (tip: `tip` in pc_stage_off)."""
    out = []
    for nid, label in stage_switches(graph):
        spec = graph[nid]["_meta"]["pc_stage_off"]
        strength = None
        if spec.get("strength"):    # a stage that is a LoRA loader: the window shows a strength slider for it
            v = graph[nid].get("inputs", {}).get("strength_model")
            strength = float(v) if isinstance(v, (int, float)) else 1.0
        out.append({"id": nid, "label": label, "tip": str(spec.get("tip", "")), "default_on": bool(spec.get("default_on", True)),
                    "strength": strength})
    return out


def set_stage_strengths(graph: dict, values: dict) -> dict:
    """{stage node id: strength}: the LoRA loaders of those stages run at that strength (a copy is returned)."""
    g = json.loads(json.dumps(graph))
    for nid, v in (values or {}).items():
        inp = g.get(str(nid), {}).get("inputs", {})
        if "strength_model" in inp and not isinstance(inp["strength_model"], list):
            inp["strength_model"] = round(float(v), 3)
    return g


def lora_tip(graph: dict) -> str:
    """The hint of the workflow's pc:lora loader (`pc_lora_tip` in its _meta): what the LoRA does and its best strength."""
    for nid in lora_switches(graph):
        tip = str(graph[nid].get("_meta", {}).get("pc_lora_tip", "")).strip()
        if tip:
            return tip
    return ""


def stage_default_on(graph: dict, nid: str) -> bool:
    """Does the stage start switched on? (`default_on` in its pc_stage_off, default true)"""
    return bool(graph.get(nid, {}).get("_meta", {}).get("pc_stage_off", {}).get("default_on", True))


def bypass_stage(graph: dict, only=None) -> dict:
    """Stage switched off: the nodes it lists are removed and the inputs it lists are set (a copy is returned).
    `only` = the node ids of the stages to switch off (None = all of them)."""
    g = json.loads(json.dumps(graph))
    for nid, _ in stage_switches(g):
        if only is not None and nid not in {str(o) for o in only}:
            continue
        spec = g[nid]["_meta"]["pc_stage_off"]
        g[nid]["inputs"].update(spec.get("set", {}))
        for r in spec.get("remove", []):
            g.pop(str(r), None)
        for r in spec.get("rewire", []):
            r = str(r)
            node = g.get(r)
            if node is None:
                continue
            src = node.get("inputs", {}).get("model")
            for other in g.values():
                for k, v in other.get("inputs", {}).items():
                    if isinstance(v, list) and v and str(v[0]) == r:
                        other["inputs"][k] = src
            g.pop(r, None)
    return g


def lora_file(name: str, available) -> str | None:
    """The name ComfyUI lists for a LoRA file, whatever the folder separator / case in the workflow ("Moss/x" vs "Moss\\x")."""
    key = lambda n: str(n).replace("\\", "/").lower()
    by_key = {key(a): a for a in available}
    if key(name) in by_key:
        return by_key[key(name)]
    tail = key(name).rsplit("/", 1)[-1]       # same file name in another folder
    hits = [a for k, a in by_key.items() if k.rsplit("/", 1)[-1] == tail]
    return hits[0] if len(hits) == 1 else None


def fix_lora_names(graph: dict, available) -> tuple[dict, list[str]]:
    """Every LoRA loader gets the file name the ComfyUI server lists (Windows: "Moss\\lenovo_moss.safetensors"). Returns
    (graph, names that were not found)."""
    g = json.loads(json.dumps(graph))
    missing = []
    for n in g.values():
        inp = n.get("inputs", {}) if isinstance(n, dict) else {}
        if n.get("class_type") in ("LoraLoader", "LoraLoaderModelOnly") if isinstance(n, dict) else False:
            name = inp.get("lora_name")
            if isinstance(name, str):
                real = lora_file(name, available)
                if real:
                    inp["lora_name"] = real
                else:
                    missing.append(name)
    return g, missing


def list_templates(folder: str | Path) -> list[Path]:
    folder = Path(folder).expanduser()
    return sorted(folder.glob("*.json")) if folder.is_dir() else []
