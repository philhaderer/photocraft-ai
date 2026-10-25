"""Orchestration: PhotoCraft → (image + mask) → ComfyUI → new layer back in PhotoCraft.

Flow for inpaint ("Generative Fill"):
  1. Remember the active document and check the selection (document.inspect).
  2. image.duplicate {mergedOnly} → a flattened copy that keeps the selection.
     Save the composite to PNG (app.save); on the copy, fill a new layer white inside the
     selection over a black background and save that as the mask. Close the copy.
  3. In Python: crop around the mask with some context, scale to ~the model's resolution.
  4. Upload to ComfyUI, queue, wait, download the results.
  5. For each result: save PNG → app.open → Select All + Copy → close → back to the document →
     Paste at the crop position, then paste a soft mask into the new layer's layer mask
     (or Edit › Paste Special › Paste Into for a hard mask from the selection).

Outpaint: the user extends the canvas visually (Crop tool, transparent extension); the bridge finds
the empty area, selects it with an overlap onto the original, then the same as inpaint.
"""

from __future__ import annotations

import dataclasses
import json
import os
import random
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from . import imaging, workflows
from .comfy import ComfyUI
from .photocraft import PhotoCraft, PhotoCraftError

MODES = ("inpaint", "remove", "reference", "outpaint", "img2img", "edit", "txt2img", "upscale", "refine")
SCALE_MODES = ("upscale", "refine")   # the picture goes to the workflow at its own size; the workflow sets the result's size
MAX_RESULT_MP = 24.0                  # Upscale: refuse results above this many megapixels
LAYER_MASKS = ("auto", "soft", "selection", "none")


class BridgeError(RuntimeError):
    pass


@dataclass
class Request:
    mode: str = "inpaint"
    params: workflows.GenParams = field(default_factory=workflows.GenParams)
    workflow: str | None = None          # None = built-in graph, else path to an API-format JSON
    base_res: int = 1024                 # side of a square with the generation's area (SD1.5: 512–768, SDXL/Flux: 1024)
    context: float = 0.4                 # context around the mask (fraction of the selection's longer side)
    mask_grow: int = 8                   # px (document scale) the model mask is grown by
    mask_blur: int = 8                   # px the model mask is blurred by
    outpaint: tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom (px)
    overlap: int = 48                    # outpaint overlap onto the existing image (px)
    variants: int = 1
    fooocus: bool = True                 # inpaint/outpaint: Fooocus patch (SDXL) when the server has it
    remove: bool = False                 # "Remove" (the bridge runs it as an inpaint with the removal instruction)
    remove_tries: int = 3                # tries (new seed each) until the object is really gone
    enhance: bool = True                 # text-model workflows: let the text model write the prompt (off = typed text as is)
    turbo: bool = True                   # workflows with a speed (turbo) LoRA, nodes titled pc:lora: off = cut it out, full steps
    layer_mask: str = "auto"             # "auto" = none for Fill with an editor that ignores the mask, else soft;
                                         # "soft" = same mask the model got, "selection" = hard selection, "none"
    feather_pct: float = 2.0             # soft layer mask for editors that ignore the mask: % of the selection's shorter side
    scale: float = 2.0                   # Upscale: factor per side (Refine always runs at 1.0)
    ref_style: str = "simple"            # reference mode: "classic" = subject first (<image_1>), long instruction, rough placement;
                                         # "simple" = the picture first (image1), the reference second (image2), one short sentence
    ref_collage: bool = True             # reference mode: also paste a rough copy of the reference where it should go
    lora_strength: float | None = None   # strength of the workflow's pc:lora loader (None = what the workflow has)
    stage_on: bool = True                # workflows with a switchable stage (pc_stage_off, e.g. SeedVR2): False = skip the first one
    stages_off: list = field(default_factory=list)   # node ids of more stages (pc_stage_off) to skip: an optional LoRA, SLG ...
    detail: float = 1.0                  # Upscale/Refine: share of the new result mixed with the plainly scaled original (1 = all new)
    ref_cutout: bool = True              # reference mode, simple style: the sentence also asks to remove the reference's background
    loras: list = field(default_factory=list)   # extra LoRAs [(file name, strength), ...] chained in front of the samplers
    match: float = 0.0                   # 0..1: pull colours that are louder than the surroundings back towards them (Fill / Expand / Reference)
    sharpen: float = 0.0                 # 0..1: a light sharpening of the result (high-pass style, like KJNodes' Image Sharpen)
    sampler_override: dict = field(default_factory=dict)   # {"steps": .., "cfg": .., "denoise": ..} typed over the workflow's sampler
    doc_tag: str = ""                    # Upscale: model and options in the new document's name ("Flux3Klein x1.5 SeedVR2")
    label: str = ""                      # added to the layer names (a comparison run: "res 1024")
    preset: str = ""                     # name of the preset used: the layers are named "<preset> #<run_no>"
    run_no: int = 0                      # running number of this preset's runs (kept by the window)


PLACEHOLDER = "<DESCRIBE THE IMAGE>"


def strip_placeholder(text: str) -> str:
    """Presets put <DESCRIBE THE IMAGE> into the prompt where a short description of the picture helps the result. Whoever
    does not replace it sends nothing: the marker itself is never part of a prompt."""
    return re.sub(r"\s{2,}", " ", (text or "").replace(PLACEHOLDER, "")).strip()


# progress(overall_fraction, message, phase="", phase_fraction=-1.0, elapsed=0.0)
#   phase is "prepare", "prompt" (a text model writes the prompt), "image" (the image model) or "place".
#   phase_fraction is -1 when the phase has no real progress (the UI then shows elapsed time / an estimate).
Progress = Callable[..., None]

WRITER_SKIP = ("TextEncode", "CLIPTextEncode", "AUSBOSS_NODES_Text")


def prompt_phase_nodes(graph: dict) -> set[str]:
    """Ids of the nodes that belong to "writing the prompt": a pc:prompt node that is a text model
    (not a plain text encoder) and everything upstream of it (loaders, image, system prompt)."""
    import re
    writers = [nid for nid, n in graph.items()
               if "prompt" in re.findall(r"pc:\s*([a-z]+)", n.get("_meta", {}).get("title", "").lower())
               and not n.get("class_type", "").startswith(WRITER_SKIP)]
    seen: set[str] = set()
    todo = list(writers)
    while todo:
        nid = todo.pop()
        if nid in seen or nid not in graph:
            continue
        seen.add(nid)
        for v in graph[nid].get("inputs", {}).values():
            if isinstance(v, list) and v and isinstance(v[0], str):
                todo.append(v[0])
    return seen if writers else set()


def mask_is_used(graph: dict) -> bool:
    """True when a pc:mask node feeds another node. Instruction-based editors (Fibo) load the mask but ignore it."""
    import re
    ids = {nid for nid, n in graph.items()
           if "mask" in re.findall(r"pc:\s*([a-z]+)", n.get("_meta", {}).get("title", "").lower())}
    return any(isinstance(v, list) and v and str(v[0]) in ids
               for n in graph.values() for v in n.get("inputs", {}).values())


def effective_layer_mask(choice: str, mode: str, editor: bool, has_sel: bool) -> str:
    """The layer mask that is really used. "auto" = none for a Fill with an instruction-based editor (Fibo): it
    regenerates the whole crop and ignores the mask, so a layer mask would cut off parts it changed on purpose
    (a person's shadow, outline, pose). Everything else gets the soft mask."""
    if not has_sel:
        return "none"
    if choice == "auto":
        return "none" if (editor and mode in ("inpaint", "reference", "outpaint")) else "soft"
    return choice


REFERENCE_PROMPT = ("Place the subject from <image_1> into <image_2>. Keep the subject exactly as it looks in <image_1> "
                    "(face, hair, clothing, colours, proportions) and match the lighting, colours and shadows of "
                    "<image_2>. Keep everything else in <image_2> unchanged.")
REFERENCE_COLLAGE_NOTE = (" A rough copy of the subject is already pasted into <image_2>: keep the subject at exactly "
                          "that position and size and make it blend into the scene.")


def reference_prompt(typed: str, collage: bool, where: str = "") -> str:
    """The instruction for "insert reference image". Fibo 2 Edit composes best with the subject first: <image_1> is the
    reference, <image_2> the picture (live tests: with the picture first the model redraws the reference and ignores
    the scene). With the rough placement the pasted copy shows where; otherwise `where` (reference_where) says it."""
    text = REFERENCE_PROMPT + (REFERENCE_COLLAGE_NOTE if collage else where)
    if typed.strip():
        text += " " + typed.strip()
    return text


def simple_reference_prompt(typed: str, where: str, cutout: bool = False) -> str:
    """The "simple" style, from a live test that worked (Fibo 2 Edit Turbo, a tower into a landscape without cutting it
    out): the picture is image1, the reference image2, and one plain sentence says where it goes."""
    text = f"Put the subject from image2 into the {where} of the picture from image1."
    if cutout:   # the reference needs no cutting out beforehand: the model removes its background itself
        text += " Remove the background of image2 first."
    if typed.strip():
        text += " " + typed.strip()
    return text


def _where(sel: "imaging.Box", crop: "imaging.Box") -> tuple[str, int]:
    """Where the selection lies inside the crop in words, and the share of the crop it covers in percent."""
    cx = (sel.center[0] - crop.x) / max(1, crop.w)
    cy = (sel.center[1] - crop.y) / max(1, crop.h)
    horiz = "left" if cx < 0.38 else "right" if cx > 0.62 else "centre"
    vert = "upper" if cy < 0.38 else "lower" if cy > 0.62 else "middle"
    where = "centre" if (horiz == "centre" and vert == "middle") else f"{vert} {horiz}".replace("middle left", "left").replace("middle right", "right").replace("upper centre", "top centre").replace("lower centre", "bottom centre")
    return where, round(100 * sel.w * sel.h / max(1, crop.w * crop.h))


def placement_hint(sel: "imaging.Box", crop: "imaging.Box") -> str:
    """Where the selection lies inside the crop, in words, for instruction-based editors that only see the crop."""
    where, share = _where(sel, crop)
    return f" (Apply this only at the {where} of the image, in an area of roughly {share}% of the image; leave everything else as it is.)"


def reference_where(sel: "imaging.Box", crop: "imaging.Box") -> str:
    """Reference mode without the rough placement: where the subject goes in <image_2> and how large."""
    where, share = _where(sel, crop)
    return f" Put the subject at the {where} of <image_2>, covering roughly {share}% of the image."


# Live test (Fibo 2 Edit Turbo, dragon on a meadow, 3 seeds): "Erase the main subject inside the red rectangle completely,
# as if it had never been there, and paint the empty scenery behind it" removed it every time. Failed: "Remove the object
# marked by the red outline ...", "... inside the red frame ... the red frame must not appear" (the model removed the
# frame and kept the subject). What works is a command to erase and to paint the scenery behind.
# Multi-part figure (knight with weapon, tight frame): "Erase the main subject ..." left head-less legs standing; naming
# "every part of it, its limbs, clothing, accessories and anything it holds" removed all of it in one pass (2 seeds).
REMOVE_PROMPT = ("Erase everything inside the red {shape} completely: the whole subject from top to bottom, including "
                 "every part of it, its limbs, clothing, accessories and anything it holds. Paint the empty scenery "
                 "behind it. Also remove the red {shape} itself.")


# Second wording, used for the second try: on a big table with food on it (tight frame) the first one changed nothing,
# this one removed the table and most of what stood on it (but it left the legs of a knight standing). Neither wording
# works everywhere, so the tries alternate A, B, A.
REMOVE_PROMPT_ALT = ("Erase everything inside the red {shape} completely: the whole object including everything standing "
                     "or lying on it and everything attached to it. Paint the empty scenery behind it, continuing the "
                     "surroundings. Also remove the red {shape} itself.")


def remove_prompt(mask: "Image.Image", attempt: int = 0) -> str:
    """The removal instruction; "rectangle" for a rectangular selection (tested), otherwise "outline"."""
    return (REMOVE_PROMPT_ALT if attempt % 2 else REMOVE_PROMPT).format(shape=_shape(mask))


def _shape(mask: "Image.Image") -> str:
    box = imaging.mask_bbox(mask)
    rect = bool(box) and (np.asarray(mask.convert("L")) > 127).sum() >= 0.97 * box.w * box.h
    return "rectangle" if rect else "outline"


# Generative fill with an instruction editor (Fibo ignores the mask): the selection is drawn into the picture as a red
# outline and this fixed sentence wraps the typed text. Live test (meadow + lake, "a red fox", "a campfire with a pot",
# "a rowing boat", "a heron"): the objects appeared at the marked spot; without the outline they appeared anywhere.
FILL_PROMPT = ("{text}. Place it only inside the red {shape}, scaled to fit it and blended into the scene "
               "(light, shadows, perspective). Do not change anything outside the red {shape}. "
               "Also remove the red {shape} itself.")


def fill_prompt(text: str, mask: "Image.Image") -> str:
    return FILL_PROMPT.format(text=text.strip().rstrip(".!"), shape=_shape(mask))


def outline_width(gen_w: int, gen_h: int) -> int:
    """Half thickness of the red outline in the generated picture: visible, but thin."""
    return max(2, round(max(gen_w, gen_h) / 300))


def outpaint_hint(keep: "imaging.Box", canvas: tuple[int, int]) -> str:
    """For instruction-based editors (Fibo), which ignore the mask: say what the white margin is."""
    W, H = canvas
    sides = [name for name, added in (("left", keep.x > 0), ("top", keep.y > 0),
                                      ("right", keep.x + keep.w < W), ("bottom", keep.y + keep.h < H)) if added]
    where = ", ".join(sides[:-1]) + " and " + sides[-1] if len(sides) > 1 else (sides[0] if sides else "")
    return (f" (The white margin on the {where} of the image is empty canvas. Extend the scene seamlessly into it, "
            "continuing what is visible at its edge, and leave no white. Keep the existing picture unchanged.)")


def outpaint_prompt(prompt: str, enhance: bool, keep: "imaging.Box", canvas: tuple[int, int]) -> str:
    """The instruction for an outpaint with an instruction editor: the typed description, "replace white" (live test:
    Fibo needs these words) and the explanation of what the white margin is. Live test, enhancement off: the short
    suffix alone did not fill the margin, the explanation has to stay. `enhance` is unused on purpose: both paths get
    the same text, so a workflow without a text model (whose checkbox keeps its value) behaves the same."""
    prompt = prompt.strip()
    if "replace white" not in prompt.lower():
        prompt += ", replace white" if prompt else "Replace white"
    return prompt + outpaint_hint(keep, canvas)


def after_prompt_nodes(graph: dict) -> set[str]:
    """Ids of the nodes that consume the written prompt (text encoder, sampler, decode, output ...)."""
    import re
    done = {nid for nid, n in graph.items()
            if "prompt" in re.findall(r"pc:\s*([a-z]+)", n.get("_meta", {}).get("title", "").lower())
            and not n.get("class_type", "").startswith(WRITER_SKIP)}
    if not done:
        return set()
    after: set[str] = set()
    changed = True
    while changed:
        changed = False
        for nid, n in graph.items():
            if nid in after or nid in done:
                continue
            links = [v[0] for v in n.get("inputs", {}).values() if isinstance(v, list) and v and isinstance(v[0], str)]
            if any(l in done or l in after for l in links):
                after.add(nid)
                changed = True
    return after


class Bridge:
    def __init__(self, pc: PhotoCraft, comfy: ComfyUI, exchange_dir: str | Path, keep_files: bool = False):
        self.pc = pc
        self.comfy = comfy
        self.exchange = Path(exchange_dir).expanduser()
        self.exchange.mkdir(parents=True, exist_ok=True)
        self.keep_files = keep_files
        self.pipeline = ""
        self.last_vgl = ""
        self._cancel = threading.Event()
        self._tmp: list[Path] = []
        self._snap: dict | None = None          # history snapshot taken before the last generation (for "Undo AI edit")
        self._snap_error = ""
        self._redo: dict | None = None          # snapshot of the state before an undo, for "Redo AI edit"
        self._last_expand: dict | None = None   # the last Expand: document, canvas size, where the original lies, result layers

    def cancel(self) -> None:
        self._cancel.set()

    # ---------- main operation ----------

    def run(self, req: Request, progress: Progress | None = None) -> dict:
        progress = progress or (lambda f, m, **kw: None)
        self._cancel.clear()
        if req.mode not in MODES:
            raise BridgeError(f"Unknown mode: {req.mode}")
        if req.mode == "remove":
            req = dataclasses.replace(req, mode="inpaint", remove=True)
        p = req.params
        p.prompt = strip_placeholder(p.prompt)   # the unedited "<DESCRIBE THE IMAGE>" of a preset is no instruction
        if p.seed is None or p.seed < 0:
            p.seed = random.randint(0, 2**31 - 1)
        p.batch = max(1, int(req.variants))
        tag = uuid.uuid4().hex[:8]
        _wfs = workflows.resolve(req.workflow) if req.workflow else [None]
        self.last_vgl = ""
        if req.mode == "reference" and not (req.workflow and all(
                workflows.has_ref_slot(workflows.load_template(w)) for w in _wfs)):
            raise BridgeError("Insert reference image needs a workflow with a reference slot (the Fibo workflows have one).")
        if req.mode in SCALE_MODES:
            if not (req.workflow and all(workflows.has_upscale_slot(workflows.load_template(w)) for w in _wfs)):
                raise BridgeError("Upscale and Refine need a workflow that sets the result's size (a node titled "
                                  "pc:upscale), e.g. flux3-klein-upscale.json.")
            if req.mode == "upscale" and not 1.0 <= float(req.scale) <= 8.0:
                raise BridgeError("Upscale factor: between 1 and 8.")
        if req.enhance and req.mode not in ("reference",) + SCALE_MODES and not p.prompt.strip() and not self._kind(req, p, _wfs):
            for w in _wfs:
                if w and prompt_phase_nodes(json.loads(Path(w).read_text(encoding="utf-8"))):
                    raise BridgeError("Type an instruction first: this workflow's text model writes the prompt from it "
                                      "(e.g. \"a large helicopter on the meadow\"). An empty one gives an arbitrary image.")
        try:
            return self._run(req, p, tag, progress)
        except PhotoCraftError as e:
            raise BridgeError(str(e)) from None
        finally:
            self._cleanup()

    @staticmethod
    def _kind(req: Request, p, wfs: list) -> str:
        """"remove": Remove, only with an instruction editor (a workflow that does not use the mask, i.e. Fibo): the
        selection is drawn into the picture as a red outline and a fixed instruction says what to do. "" = a normal run.
        Generative fill with an editor and no text is an error: Remove is the way to take something away."""
        if req.mode != "inpaint" or not wfs or not wfs[0]:
            if req.remove:
                raise BridgeError("Remove needs a Fibo workflow (pick one in the Workflow list).")
            return ""
        editor = not any(mask_is_used(json.loads(Path(w).read_text(encoding="utf-8"))) for w in wfs)
        if req.remove:
            if not editor:
                raise BridgeError("Remove needs a Fibo workflow, this one uses the mask to inpaint.")
            return "remove"
        if editor and not p.prompt.strip():
            raise BridgeError("Generative fill needs a text: describe what should appear in the selection "
                              "(\"a helicopter on the meadow\"). To take something away use \"Remove\".")
        return ""

    # ---------- waiting for ComfyUI, with separate prompt / image phases ----------

    def _timings_file(self) -> Path:
        return self.exchange / "timings.json"

    def _load_timings(self) -> dict:
        try:
            return json.loads(self._timings_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_timing(self, key: str, seconds: float) -> None:
        t = self._load_timings()
        t[key] = round(seconds, 1)
        try:
            self._timings_file().write_text(json.dumps(t, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _wait(self, prompt_id, graph, wf, start, span, suffix, progress):
        """comfy.wait with the work split in "prompt" (text model) and "image" (the image model), each with its
        own fraction, elapsed time and, once a run has been timed, an estimate for the text phase."""
        writer = prompt_phase_nodes(graph)
        after = after_prompt_nodes(graph)
        key = (Path(wf).stem if wf else "builtin") + ":prompt"
        expected = self._load_timings().get(key)
        t0 = time.monotonic()
        marks = {"phase": None, "since": t0, "prompt_secs": None}

        def on(f, msg, node=None):
            now = time.monotonic()
            if writer and node in after and marks["prompt_secs"] is None:
                marks["prompt_secs"] = now - t0
                self._save_timing(key, marks["prompt_secs"])
            phase = "prompt" if (writer and marks["prompt_secs"] is None) else "image"
            if phase != marks["phase"]:
                marks["phase"], marks["since"] = phase, now
            elapsed = now - marks["since"] if phase == "prompt" else now - t0 - (marks["prompt_secs"] or 0)
            if phase == "prompt":
                pf = min(0.95, elapsed / expected) if expected else -1.0
                text = f"Expanding Prompt… {elapsed:.0f} s" + (f" (usually ~{expected:.0f} s)" if expected else "")
                overall = start + span * 0.3 * (pf if pf >= 0 else 0)
            else:
                if f >= 0:
                    marks["img_f"] = f
                    marks["img_msg"] = msg
                # between two sampler steps ComfyUI is silent: keep the last real value instead of flipping
                # the bar back to "unknown" (that made it blink)
                pf = marks.get("img_f", -1.0)
                text = (marks.get("img_msg") or "Generating the image…") if pf >= 0 else f"Generating the image… {elapsed:.0f} s"
                share = 0.3 if writer else 0.0
                overall = start + span * (share + (1 - share) * pf) if pf >= 0 else -1
            progress(overall, text + suffix, phase=phase, phase_fraction=pf, elapsed=elapsed)

        return self.comfy.wait(prompt_id, on_progress=on, cancelled=self._cancel.is_set)

    def _run(self, req: Request, p: workflows.GenParams, tag: str, progress: Progress) -> dict:
        pc = self.pc.connect()
        sess = pc.session()
        orig = sess.get("active")
        if orig is None:
            raise BridgeError("Open a document in PhotoCraft first.")
        orig_name = sess["documents"][orig]["name"]
        if req.mode != "upscale":   # Upscale only opens a new document: nothing to undo in this one
            self._snapshot(orig_name)   # one click back to here, however many history steps the run adds
        doc = pc.document()

        keep = None  # outpaint: where the original image lies in the extended canvas
        if req.mode == "outpaint":
            progress(0.02, "Finding the empty canvas area", phase="prepare")
            keep = self._select_new_area(req, orig, tag)
            doc = pc.document()

        W, H = doc["width"], doc["height"]
        has_sel = bool(doc.get("hasSelection")) and req.mode not in ("edit", "txt2img")   # these work on the whole canvas, a selection is ignored
        if req.mode == "inpaint" and not has_sel:
            raise BridgeError("Select the area to fill first (e.g. Lasso or Rectangular Marquee).")
        if req.mode == "reference":
            if len(doc.get("layers", [])) < 2:
                raise BridgeError("Put the reference image on its own layer above the picture: the top layer is the reference.")

        wf_paths = workflows.resolve(req.workflow) if req.workflow else [None]
        # an instruction-based editor (Fibo) never sees the mask: it gets the white margin as it is plus a sentence
        # saying what it is; a smeared edge fill would look finished to it and come back unchanged
        editor = bool(wf_paths[0]) and not any(mask_is_used(json.loads(Path(w).read_text(encoding="utf-8")))
                                               for w in wf_paths)

        if req.mode == "edit" and not (wf_paths[0] and editor):
            raise BridgeError("Edit whole image needs an instruction-based edit workflow (Fibo, Qwen Image 2.1 Edit, Flux 2/3 Klein edit).")
        if req.mode == "edit" and not p.prompt.strip():
            raise BridgeError("Describe the edit in the prompt (it applies to the whole picture).")
        if req.mode == "txt2img" and not p.prompt.strip():
            raise BridgeError("Describe the picture in the prompt.")
        if editor and p.denoise != 1.0:
            # live test (Image → image at 0.6): an instruction editor starts from an empty latent, so a denoise below 1.0
            # gives a broken picture (a whole creek of ducks); at 1.0 the same instruction edits the picture correctly
            p.denoise = 1.0

        src = mask = None
        if req.mode != "txt2img" or has_sel:
            progress(0.05, "Exporting the image from PhotoCraft", phase="prepare")
            ref_rgba = ref_rgb = None
            if req.mode == "reference":
                try:
                    ref_full = self._export_top_layer(orig, tag)
                    ref_rgba, ref_rgb = imaging.reference_from_layer(ref_full)
                except ValueError as e:
                    raise BridgeError(str(e)) from None
            src, mask = self._export(orig, tag, need_mask=has_sel, drop_top=(req.mode == "reference"))
            if req.mode == "reference" and mask is None:
                # no selection: the reference layer, placed where it belongs, is the place (and its size)
                lb = imaging.layer_box(ref_full)
                if lb is None or ref_full.size != (W, H):
                    raise BridgeError("Select where the reference image should go (e.g. Rectangular Marquee), or place its layer there.")
                mask = Image.new("L", (W, H), 0)
                mask.paste(255, lb.pil())
                has_sel = True
            if keep is not None:
                src = imaging.white_outside(src, keep) if editor else imaging.clear_outside(src, keep)

        bbox = None
        if req.mode in ("inpaint", "reference", "outpaint"):
            bbox = imaging.mask_bbox(mask)
            if bbox is None:
                raise BridgeError("The selection is empty.")
            region = imaging.grow_box(bbox, (W, H), req.context)
        elif has_sel:
            region = imaging.mask_bbox(mask) or imaging.Box(0, 0, W, H)
        else:
            region = imaging.Box(0, 0, W, H)

        removal = self._kind(req, p, wf_paths)
        fill = bool(editor and req.mode == "inpaint" and has_sel and not removal and p.prompt.strip())
        marked = bool(removal) or fill
        if req.mode in SCALE_MODES:   # the picture goes in at its own size, the workflow sets the size of the result
            gw, gh = region.w, region.h
            factor = float(req.scale) if req.mode == "upscale" else 1.0
            mp = region.w * region.h * factor * factor / 1e6
            if mp > MAX_RESULT_MP:
                raise BridgeError(f"The result would be {mp:.0f} megapixels ({region.w * factor:.0f}×{region.h * factor:.0f}); "
                                  f"the limit is {MAX_RESULT_MP:.0f}. Select a smaller area or use a smaller factor.")
            p.extra["megapixels"] = mp
        else:
            mult = max(workflows.size_multiple(workflows.load_template(w)) for w in wf_paths if w) if wf_paths[0] else 16
            gw, gh = imaging.gen_size(region.w, region.h, req.base_res, multiple=mult)
        p.width, p.height = gw, gh
        progress(0.1, f"Sending to ComfyUI ({gw}×{gh})", phase="prepare")

        image_name = mask_name = None
        if req.mode != "txt2img":
            crop_full = src.crop(region.pil())
            if req.mode == "reference" and req.ref_collage and req.ref_style != "simple":
                crop_full = imaging.paste_reference(crop_full, ref_rgba, imaging.Box(bbox.x - region.x, bbox.y - region.y, bbox.w, bbox.h))
            crop = imaging.to_rgb(crop_full).resize((gw, gh), Image.LANCZOS)
            crop_plain = crop
            if marked:
                crop = imaging.mark_outline(crop, mask.crop(region.pil()).resize((gw, gh), Image.NEAREST), outline_width(gw, gh))
            image_name = self.comfy.upload_image(crop, f"pcc-{tag}-image.png")
        ref_name = None
        if req.mode == "reference":
            ref_name = self.comfy.upload_image(ref_rgb, f"pcc-{tag}-ref.png")
        if req.mode in ("inpaint", "reference", "outpaint"):
            m = imaging.prepare_mask(mask.crop(region.pil()), req.mask_grow, req.mask_blur)
            m = m.resize((gw, gh), Image.BILINEAR)
            mask_name = self.comfy.upload_image(m.convert("RGB"), f"pcc-{tag}-mask.png")

        hint = placement_hint(bbox, region) if (req.mode == "inpaint" and has_sel and bbox) else ""
        n_wf = len(wf_paths)
        results: list[tuple[str, list[Image.Image]]] = []
        for k, wf in enumerate(wf_paths):
            # several workflows (a group) run one after another with the same crop, mask and seed
            label = Path(wf).stem.split("-")[-1] if (wf and n_wf > 1) else ""
            suffix = f" [{label}]" if label else ""
            self.pipeline = "workflow" if wf else req.mode
            gp = p
            if keep is not None and editor:
                gp = dataclasses.replace(p, prompt=outpaint_prompt(p.prompt, req.enhance, keep, (W, H)))
            if req.mode == "reference":
                # the text model is bypassed in this mode: a fixed instruction with <image_1>/<image_2> (+ where)
                if req.ref_style == "simple":
                    gp = dataclasses.replace(p, prompt=simple_reference_prompt(p.prompt, _where(bbox, region)[0], req.ref_cutout))
                else:
                    gp = dataclasses.replace(p, prompt=reference_prompt(p.prompt, req.ref_collage, reference_where(bbox, region)))
            if removal:   # fixed instruction, the text model is bypassed
                gp = dataclasses.replace(p, prompt=remove_prompt(mask.crop(region.pil())))
            elif fill:    # marked area + fixed wrapper around the typed text; goes through the text model only when the
                #           workflow has one and "Enhance" is on (live test: the same placement, ~25 s slower, fewer
                #           doubled objects in 1 of 5 pictures), otherwise it is sent as it is
                gp = dataclasses.replace(p, prompt=fill_prompt(p.prompt, mask.crop(region.pil())))
            if hint and wf and req.enhance and not removal and not fill and prompt_phase_nodes(workflows.load_template(wf)):
                gp = dataclasses.replace(p, prompt=p.prompt.strip() + hint)  # text-model workflows only
            start, span = 0.15 + 0.75 * k / n_wf, 0.75 / n_wf
            tries = max(1, int(req.remove_tries)) if removal == "remove" else 1
            sel = mask.crop(region.pil()).resize((gw, gh), Image.NEAREST) if removal else None
            best = None   # (score, images, seed): the try that changed the selection most
            for attempt in range(tries):
                if attempt:   # the object is still there: same picture, new seed and the other wording
                    gp = dataclasses.replace(gp, seed=(gp.seed + 7919 * attempt) % (2**31),
                                             prompt=remove_prompt(mask.crop(region.pil()), attempt))
                    p.seed = gp.seed
                graph, out_node = self._graph(req, gp, image_name, mask_name, wf, ref_name, force_plain=marked and not (fill and req.enhance and prompt_phase_nodes(workflows.load_template(wf))))
                prompt_id = self.comfy.queue(graph)
                progress(start, f"Queued in ComfyUI ({self.pipeline}{suffix})" if not attempt
                         else f"Object still there, trying again ({attempt + 1}/{tries})", phase="prepare")
                hist = self._wait(prompt_id, graph, wf, start, span, suffix, progress)
                vgl = self._vgl_text(graph, hist)
                if vgl:
                    self.last_vgl = vgl
                ims = self.comfy.output_images(hist, out_node)[: max(1, req.variants)]
                if tries == 1 or not ims:
                    break
                score = imaging.removal_score(crop_plain, ims[0], sel, outline_width(gw, gh))
                if best is None or score > best[0]:
                    best = (score, ims, gp.seed)
                if score >= imaging.REMOVAL_MIN:
                    break
            if best is not None and best[1] is not ims:   # the last try was not the best one: keep the best
                ims, p.seed = best[1], best[2]
            results.append((label, ims))

        if req.mode in SCALE_MODES and req.detail < 0.999:
            # tame an over-sharp result: mix it with the plainly (Lanczos) scaled original
            plain = imaging.to_rgb(crop_full)
            results = [(lb, [Image.blend(plain.resize(im.size, Image.LANCZOS), im.convert("RGB"), max(0.0, req.detail)) for im in ims])
                       for lb, ims in results]
        progress(0.92, "Placing the result in PhotoCraft", phase="place")
        if req.mode == "upscale":
            return self._open_upscaled(results, orig, orig_name, region, p, tag, progress, req)
        orig = self._find_doc(orig, orig_name)
        base = (p.prompt.strip() or ("object" if req.remove else req.mode))[:40]
        mode_name = "remove" if req.remove else req.mode
        layer_mask = None
        lm_mode = effective_layer_mask(req.layer_mask, req.mode, editor, has_sel)
        if lm_mode == "soft":
            if wf_paths[0] and not any(mask_is_used(json.loads(Path(w).read_text(encoding="utf-8"))) for w in wf_paths):
                # an editor that regenerated the whole crop and never saw the mask (Fibo): feather by a share of
                # the selection's size (a feather already set in PhotoCraft is kept as it is)
                sel = bbox or region
                layer_mask = imaging.auto_feather(mask.crop(region.pil()),
                                                  imaging.feather_radius(sel.w, sel.h, req.feather_pct))
            else:
                # the same soft mask the model got: the result blends exactly where the model blended it
                layer_mask = imaging.prepare_mask(mask.crop(region.pil()), req.mask_grow, req.mask_blur)
        mode = lm_mode
        sel_small = None   # the new area in the size the model drew it, for "match colours"
        if req.match > 0 and req.mode in ("inpaint", "outpaint", "reference") and mask is not None and results and results[0][1]:
            sel_small = mask.crop(region.pil()).resize(results[0][1][0].size, Image.NEAREST)
        items = [(label, i, im, len(ims)) for label, ims in results for i, im in enumerate(ims)]
        layers = []
        # last item first: #1 ends up on top, visible and active, the others hidden below it
        for n, g in enumerate(reversed(range(len(items)))):
            label, i, raw, count = items[g]
            rgb = raw.convert("RGB")
            if req.match > 0 and sel_small is not None:
                rgb = imaging.match_saturation(rgb, crop_plain, sel_small, req.match)
            im = rgb.resize((region.w, region.h), Image.LANCZOS)
            im = imaging.sharpen(im, req.sharpen)
            label = " ".join(x for x in (label, req.label) if x)
            if req.preset:
                name = f"{req.preset} #{req.run_no}" + (f".{i + 1}" if count > 1 else "") + (f" [{label}]" if label else "")
            else:
                name = (f"AI {mode_name}" + (f" [{label}]" if label else "") + f": {base} [{p.seed}]"
                        + (f" #{i + 1}" if count > 1 else ""))
            layers.insert(0, self._import(orig, im, region, mode, name, tag, g, first=(n == 0), hidden=(g > 0),
                                          layer_mask=layer_mask))
        if req.mode == "outpaint":
            self._last_expand = {"doc": orig_name, "size": (W, H), "keep": keep, "layers": list(layers)}
            self._try("select.deselect")   # the new-area selection is not needed any more; a rerun finds the area again
        elif has_sel:
            self._try("select.reselect")  # selection comes back, ready for another generation
        progress(1.0, f"Done (seed {p.seed})", phase="place")
        return {"seed": p.seed, "vgl": self.last_vgl, "layers": layers, "region": region.__dict__, "size": [gw, gh], "pipeline": self.pipeline}

    # ---------- ComfyUI ----------

    @staticmethod
    def _vgl_text(graph: dict, hist: dict) -> str:
        """Text produced by nodes titled pc:vgl (a PreviewAny after the prompt writer), for display in the GUI."""
        import re
        for nid, n in graph.items():
            if "vgl" in re.findall(r"pc:\s*([a-z]+)", n.get("_meta", {}).get("title", "").lower()):
                text = (hist.get("outputs", {}).get(nid) or {}).get("text")
                if text:
                    return "\n".join(str(t) for t in text)
        return ""

    def _real_lora_names(self, tpl: dict) -> dict:
        """The LoRA files of the workflow under the names this ComfyUI lists (Windows: "Moss\\x.safetensors"); a file the
        server does not have stops the run with its name instead of ComfyUI's "value not in list"."""
        try:
            available = self.comfy.loras()
        except Exception:
            return tpl
        if not available:
            return tpl
        tpl, missing = workflows.fix_lora_names(tpl, available)
        if missing:
            raise BridgeError("ComfyUI does not list this LoRA file: " + ", ".join(missing)
                              + ". Put it in the LoRA folder (or switch the LoRA off) and press Refresh.")
        return tpl

    def _graph(self, req: Request, p, image_name, mask_name, wf: str | None = None, ref_name: str | None = None,
               force_plain: bool = False):
        if wf:
            tpl = workflows.load_template(wf)
            if not req.enhance or req.mode == "reference" or force_plain:
                # first: without the text model, a picture it alone needed (Text to image) is not required either
                tpl = workflows.bypass_prompt_writer(tpl, p.prompt)
            if not req.turbo:
                tpl = workflows.bypass_lora(tpl)
            elif req.lora_strength is not None:
                tpl = workflows.set_lora_strength(tpl, req.lora_strength)
            off = [str(x) for x in req.stages_off]
            if not req.stage_on:
                first = next((nid for nid, _ in workflows.stage_switches(tpl)), None)
                if first is not None:
                    off.append(first)
            if off:
                tpl = workflows.bypass_stage(tpl, off)
            if req.sampler_override:
                tpl = workflows.set_sampler(tpl, **{k: v for k, v in req.sampler_override.items() if k in ("steps", "cfg", "denoise")})
            if req.loras:
                tpl = workflows.add_loras(tpl, req.loras)
            names = getattr(self, "_real_lora_names", None)
            if names:
                tpl = names(tpl)
            return workflows.apply_template(tpl, p, image_name, mask_name, ref_name,
                                            ref_first=req.ref_style != "simple")
        if not p.checkpoint:
            raise BridgeError("Pick a model (checkpoint) or a custom workflow.")
        if req.mode == "txt2img":
            return workflows.txt2img(p), "out"
        if req.mode == "img2img":
            return workflows.img2img(p, image_name), "out"
        if req.fooocus:
            files = self.comfy.fooocus_inpaint()
            if files:
                self.pipeline = "Fooocus inpaint"
                fill = "blur" if req.mode == "outpaint" else "neutral"
                return workflows.inpaint_fooocus(p, image_name, mask_name, *files, fill=fill), "out"
        self.pipeline = "inpaint"
        return workflows.inpaint(p, image_name, mask_name), "out"

    # ---------- PhotoCraft ----------

    def _path(self, tag: str, suffix: str) -> tuple[str, Path]:
        name = f"pcc-{tag}-{suffix}.png"
        full = self.exchange / name
        self._tmp.append(full)
        return name, full

    def _wait_file(self, full: Path, timeout: float = 30) -> Image.Image:
        # app.save waits for the write, but wait for the file too, just in case
        end = time.monotonic() + timeout
        while not full.exists() and time.monotonic() < end:
            time.sleep(0.1)
        im = Image.open(full)
        im.load()
        return im

    def _export_top_layer(self, orig: int, tag: str) -> Image.Image:
        """The top layer on its own (with its transparency), exported from a throw-away duplicate."""
        pc = self.pc
        pc.execute("image.duplicate", {"name": f"pccomfy-{tag}-ref", "mergedOnly": False})
        try:
            for layer in pc.document()["layers"][1:]:  # index 0 is the top layer
                pc.execute("layer.delete", {"layer": layer["id"]})
            name, full = self._path(tag, "ref")
            pc.save(name)
            return self._wait_file(full)
        finally:
            pc.close_active()
            pc.activate(orig)

    def _export(self, orig: int, tag: str, need_mask: bool, drop_top: bool = False) -> tuple[Image.Image, Image.Image | None]:
        """The picture (and the selection as a mask) from a throw-away duplicate. With `drop_top` the top layer (the
        reference) is left out: the picture is all layers below it, flattened in the duplicate only."""
        pc = self.pc
        pc.execute("image.duplicate", {"name": f"pccomfy-{tag}", "mergedOnly": not drop_top})
        try:
            if drop_top:
                pc.execute("layer.delete", {"layer": pc.document()["layers"][0]["id"]})
                self._try("layer.flattenImage")  # nothing to flatten when only one layer is left
            src_name, src_full = self._path(tag, "src")
            pc.save(src_name)
            mask = None
            if need_mask:
                bottom = pc.document()["layers"][-1]["id"]
                pc.execute("layer.new.layer", {"name": "mask"})
                pc.execute("edit.fill", {"contents": "white"})
                pc.execute("select.deselect")
                pc.execute("layer.select", {"layer": bottom})
                pc.execute("edit.fill", {"contents": "black"})
                pc.execute("layer.flattenImage")  # avoids the "layers flattened" warning on PNG save
                mask_name, mask_full = self._path(tag, "mask")
                pc.save(mask_name)
                mask = self._wait_file(mask_full).convert("L")
            src = self._wait_file(src_full)
        finally:
            pc.close_active()
            pc.activate(orig)
        return src, mask

    def _copy_png(self, orig: int, im: Image.Image, tag: str, suffix: str) -> None:
        """Image → PhotoCraft clipboard: save PNG, open it, Select All + Copy, close it."""
        pc = self.pc
        name, full = self._path(tag, suffix)
        im.save(full)
        pc.open(name)
        try:
            pc.execute("select.all")
            pc.execute("edit.copy")
        finally:
            pc.close_active()
            pc.activate(orig)

    def _import(self, orig: int, im: Image.Image, region: imaging.Box, mode: str, layer_name: str, tag: str, i: int,
                first: bool = True, hidden: bool = False, layer_mask: Image.Image | None = None) -> int:
        pc = self.pc
        center = list(region.center)
        self._copy_png(orig, im, tag, f"result{i}")
        if mode == "selection":
            if not first:  # pasting drops the selection – bring it back for the next variant
                pc.execute("select.reselect")
            layer = pc.execute("edit.pasteSpecial.pasteInto", {"center": center})["layer"]
        else:
            layer = pc.execute("edit.paste", {"center": center})["layer"]
            if mode == "soft" and layer_mask is not None:
                # soft, editable layer mask: a white mask, then the mask's luminosity pasted into it
                self._copy_png(orig, layer_mask.convert("RGB"), tag, f"lmask{i}")
                pc.execute("layer.select", {"layer": layer})
                pc.execute("layer.layerMask.revealAll", {"layer": layer})
                pc.execute("edit.paste", {"center": center, "target": "mask"})
        self._try("layer.renameLayer", {"layer": layer, "name": layer_name})
        if hidden:
            self._try("layer.hideLayers", {"layer": layer})
        return layer

    def _open_upscaled(self, results, orig: int, orig_name: str, region: "imaging.Box", p, tag: str, progress, req: Request | None = None) -> dict:
        """Upscale: every result becomes a new document (like Photoshop's Image Size into a new file); the original
        stays as it is. The first result is opened last, so it is the active one."""
        import re
        pc = self.pc
        stem = re.sub(r"[^\w .()+-]", "_", Path(orig_name).stem).strip() or "image"
        items = [im for _, ims in results for im in ims]
        sizes = []
        for n, im in enumerate(reversed(items)):
            k = len(items) - n
            w, h = im.size
            tag_txt = re.sub(r"[^\w .()+-]", "_", req.doc_tag if req else "").strip()
            name = f"{stem} {tag_txt + ' ' if tag_txt else ''}upscaled {w}x{h}" + (f" #{k}" if len(items) > 1 else "") + ".png"
            full = self.exchange / name
            self._tmp.append(full)
            im.convert("RGB").save(full)
            pc.open(name)
            sizes.append([w, h])
        progress(1.0, f"Done: opened as a new document (seed {p.seed})", phase="place")
        return {"seed": p.seed, "vgl": "", "layers": [], "region": region.__dict__, "size": sizes[-1],
                "pipeline": self.pipeline, "documents": len(items)}

    def _select_new_area(self, req: Request, orig: int, tag: str) -> "imaging.Box":
        """Outpaint: select the empty (transparent or white) canvas plus an overlap onto the existing image.

        The canvas is opened by the user (Crop tool, which fills it with white); the empty bands are found in the
        merged image. Returns where the original image lies.
        Explicit pixel amounts (command line, tests) are applied first with Canvas Size instead.
        """
        if any(max(0, int(v)) for v in req.outpaint):
            keep = self._expand_canvas(req)
        else:
            src, _ = self._export(orig, f"{tag}-probe", need_mask=False)
            keep = imaging.content_box(src)
            if keep is None:
                keep = self._rerun_expand(orig)   # the last result fills the margin: run the same expand again
            if keep is None:
                raise BridgeError("No empty canvas area found. Extend the canvas first (Crop tool, confirm with Enter), "
                                  "then generate again.")
        doc = self.pc.document()
        x0, y0, x1, y1 = imaging.new_area_rect(keep, (doc["width"], doc["height"]), req.overlap)
        self.pc.execute("select.all")
        if x1 > x0 and y1 > y0:
            # feather only the edge against the original (feathering the whole selection would round the canvas corners)
            self.pc.execute("select.rect", {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0,
                                            "mode": "subtract", "feather": max(0, int(req.overlap) // 2)})
        return keep

    @staticmethod
    def _snapshot_id(res):
        """The id PhotoCraft gives a new snapshot (a number or text, or inside a dict under a common key)."""
        if isinstance(res, (int, str)) and not isinstance(res, bool):
            return res
        if isinstance(res, dict):
            for key in ("id", "snapshot", "snapshotId", "snapshot_id", "index"):
                if isinstance(res.get(key), (int, str)) and not isinstance(res.get(key), bool):
                    return res[key]
            for v in res.values():   # one level deeper, e.g. {"snapshot": {"id": 3}}
                if isinstance(v, dict):
                    found = Bridge._snapshot_id(v)
                    if found is not None:
                        return found
        return None

    def _snapshot(self, doc_name: str) -> None:
        """History snapshot before the run starts. The run adds several history steps (paste, rename, mask, ...) and
        PhotoCraft has no way to group them; the snapshot is the single step back (`undo_last`). Only the latest one
        is kept. Best effort: a failure is remembered and reported when the user tries to undo.
        PhotoCraft selects and deletes a snapshot by its id, which new-snapshot returns."""
        stamp = time.strftime("Before AI %H:%M:%S")
        if self._snap and self._snap.get("id") is not None:
            self._try("history.deleteSnapshot", {"snapshot": self._snap["id"]})
        self._snap = None
        self._drop_redo()   # a new run ends the redo chain
        try:
            res = self.pc.execute("history.newSnapshot", {"name": stamp})
        except PhotoCraftError as e:
            self._snap_error = str(e)
            return
        sid = self._snapshot_id(res)
        if sid is None:
            self._snap_error = f"history.newSnapshot gave no id (answer: {json.dumps(res, default=str)[:200]})"
            return
        self._snap, self._snap_error = {"name": stamp, "doc": doc_name, "id": sid}, ""

    def _drop_redo(self) -> None:
        redo, self._redo = getattr(self, "_redo", None), None
        if redo and redo.get("id") is not None:
            self._try("history.deleteSnapshot", {"snapshot": redo["id"]})

    def _activate_doc(self, name: str):
        pc = self.pc.connect()
        docs = pc.session().get("documents", [])
        match = next((d["index"] for d in docs if d["name"] == name), None)
        if match is None:
            raise BridgeError(f"Document \u201c{name}\u201d not found \u2013 was it closed?")
        pc.activate(match)
        return pc

    def undo_last(self) -> str:
        """Go back to the snapshot taken before the last generation (one history step for the whole run). The state
        that is left is kept as a snapshot too, so "Redo" can bring it back."""
        if not self._snap:
            raise BridgeError("Nothing to undo yet." + (f" (No snapshot could be made: {self._snap_error})" if self._snap_error else ""))
        pc = self._activate_doc(self._snap["doc"])
        self._drop_redo()
        stamp = time.strftime("After AI %H:%M:%S")
        try:   # best effort: without it undo still works, redo does not
            sid = self._snapshot_id(pc.execute("history.newSnapshot", {"name": stamp}))
            if sid is not None:
                self._redo = {"name": stamp, "doc": self._snap["doc"], "id": sid}
        except PhotoCraftError:
            pass
        try:
            pc.execute("history.selectSnapshot", {"snapshot": self._snap["id"]})
        except PhotoCraftError as e:
            raise BridgeError(f"Could not go back to the snapshot: {e}") from None
        return f"Back to the state before the last AI edit ({self._snap['name']})."

    def redo_last(self) -> str:
        """Bring back the result that the last undo left (until the next generation)."""
        redo = getattr(self, "_redo", None)
        if not redo:
            raise BridgeError("Nothing to redo (redo is possible right after an undo, until the next generation).")
        pc = self._activate_doc(redo["doc"])
        try:
            pc.execute("history.selectSnapshot", {"snapshot": redo["id"]})
        except PhotoCraftError as e:
            raise BridgeError(f"Could not redo: {e}") from None
        return f"Redone: the AI edit is back ({redo['name']})."

    def _rerun_expand(self, orig: int) -> "imaging.Box | None":
        """Expand again right after an Expand whose result is not wanted: the margin is covered by that result, so no
        empty band is found any more. Same document and canvas size as the last Expand: reuse where the original lies
        and hide the previous result layers (they stay in the document, just below the new result)."""
        last = self._last_expand
        if not last:
            return None
        doc = self.pc.document()
        name = self.pc.session()["documents"][orig]["name"]
        if last["doc"] != name or tuple(last["size"]) != (doc["width"], doc["height"]):
            return None
        for layer in last["layers"]:
            self._try("layer.hideLayers", {"layer": layer})
        return last["keep"]

    def _expand_canvas(self, req: Request) -> "imaging.Box":
        """Add the requested pixels around the image; returns where the original now lies."""
        left, top, right, bottom = (max(0, int(v)) for v in req.outpaint)
        doc = self.pc.document()
        W0, H0 = doc["width"], doc["height"]
        for amount, size, anchor in ((left, "width", "right"), (right, "width", "left"),
                                     (top, "height", "bottom"), (bottom, "height", "top")):
            if amount:
                params = {"width": 0, "height": 0, "relative": True, "anchor": anchor, "extensionColor": "transparent"}
                params[size] = amount
                self.pc.execute("image.canvasSize", params)
        return imaging.Box(left, top, W0, H0)

    def _find_doc(self, index: int, name: str) -> int:
        """The user may have opened/closed tabs meanwhile – find the document by name."""
        docs = self.pc.session().get("documents", [])
        if index < len(docs) and docs[index]["name"] == name:
            return index
        for d in docs:
            if d["name"] == name:
                return d["index"]
        raise BridgeError(f"Document “{name}” not found – was it closed?")

    def _try(self, command: str, params: dict | None = None):
        try:
            return self.pc.execute(command, params)
        except PhotoCraftError:
            return None

    def _cleanup(self) -> None:
        if not self.keep_files:
            for f in self._tmp:
                try:
                    os.remove(f)
                except OSError:
                    pass
        self._tmp.clear()
