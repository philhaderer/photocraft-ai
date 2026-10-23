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

Outpaint: Canvas Size first (transparent extension), select the new area with an overlap onto
the original, then the same as inpaint.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from . import imaging, workflows
from .comfy import ComfyUI
from .photocraft import PhotoCraft, PhotoCraftError

MODES = ("inpaint", "outpaint", "img2img", "txt2img")
LAYER_MASKS = ("soft", "selection", "none")


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
    layer_mask: str = "soft"             # "soft" = same mask the model got, "selection" = hard selection, "none"


# progress(overall_fraction, message, phase="", phase_fraction=-1.0, elapsed=0.0)
#   phase is "prepare", "prompt" (a text model writes the prompt), "image" (the image model) or "place".
#   phase_fraction is -1 when the phase has no real progress (the UI then shows elapsed time / an estimate).
Progress = Callable[..., None]

WRITER_SKIP = ("TextEncode", "CLIPTextEncode")


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
        self._cancel = threading.Event()
        self._tmp: list[Path] = []

    def cancel(self) -> None:
        self._cancel.set()

    # ---------- main operation ----------

    def run(self, req: Request, progress: Progress | None = None) -> dict:
        progress = progress or (lambda f, m, **kw: None)
        self._cancel.clear()
        if req.mode not in MODES:
            raise BridgeError(f"Unknown mode: {req.mode}")
        p = req.params
        if p.seed is None or p.seed < 0:
            p.seed = random.randint(0, 2**31 - 1)
        p.batch = max(1, int(req.variants))
        tag = uuid.uuid4().hex[:8]
        try:
            return self._run(req, p, tag, progress)
        except PhotoCraftError as e:
            raise BridgeError(str(e)) from None
        finally:
            self._cleanup()

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
                text = f"Writing the prompt… {elapsed:.0f} s" + (f" (usually ~{expected:.0f} s)" if expected else "")
                overall = start + span * 0.3 * (pf if pf >= 0 else 0)
            else:
                pf = f
                text = (msg or "Generating the image…") if f >= 0 else f"Generating the image… {elapsed:.0f} s"
                share = 0.3 if writer else 0.0
                overall = start + span * (share + (1 - share) * f) if f >= 0 else -1
            progress(overall, text + suffix, phase=phase, phase_fraction=pf, elapsed=elapsed)

        return self.comfy.wait(prompt_id, on_progress=on, cancelled=self._cancel.is_set)

    def _run(self, req: Request, p: workflows.GenParams, tag: str, progress: Progress) -> dict:
        pc = self.pc.connect()
        sess = pc.session()
        orig = sess.get("active")
        if orig is None:
            raise BridgeError("Open a document in PhotoCraft first.")
        orig_name = sess["documents"][orig]["name"]
        doc = pc.document()

        if req.mode == "outpaint":
            progress(0.02, "Expanding the canvas", phase="prepare")
            self._expand_canvas(req)
            doc = pc.document()

        W, H = doc["width"], doc["height"]
        has_sel = bool(doc.get("hasSelection"))
        if req.mode == "inpaint" and not has_sel:
            raise BridgeError("Select the area to fill first (e.g. Lasso or Rectangular Marquee).")

        src = mask = None
        if req.mode != "txt2img" or has_sel:
            progress(0.05, "Exporting the image from PhotoCraft", phase="prepare")
            src, mask = self._export(orig, tag, need_mask=has_sel)

        if req.mode in ("inpaint", "outpaint"):
            bbox = imaging.mask_bbox(mask)
            if bbox is None:
                raise BridgeError("The selection is empty.")
            region = imaging.grow_box(bbox, (W, H), req.context)
        elif has_sel:
            region = imaging.mask_bbox(mask) or imaging.Box(0, 0, W, H)
        else:
            region = imaging.Box(0, 0, W, H)

        gw, gh = imaging.gen_size(region.w, region.h, req.base_res)
        p.width, p.height = gw, gh
        progress(0.1, f"Sending to ComfyUI ({gw}×{gh})", phase="prepare")

        image_name = mask_name = None
        if req.mode != "txt2img":
            crop = imaging.to_rgb(src.crop(region.pil())).resize((gw, gh), Image.LANCZOS)
            image_name = self.comfy.upload_image(crop, f"pcc-{tag}-image.png")
        if req.mode in ("inpaint", "outpaint"):
            m = imaging.prepare_mask(mask.crop(region.pil()), req.mask_grow, req.mask_blur)
            m = m.resize((gw, gh), Image.BILINEAR)
            mask_name = self.comfy.upload_image(m.convert("RGB"), f"pcc-{tag}-mask.png")

        wf_paths = workflows.resolve(req.workflow) if req.workflow else [None]
        n_wf = len(wf_paths)
        results: list[tuple[str, list[Image.Image]]] = []
        for k, wf in enumerate(wf_paths):
            # several workflows (a group) run one after another with the same crop, mask and seed
            label = Path(wf).stem.split("-")[-1] if (wf and n_wf > 1) else ""
            suffix = f" [{label}]" if label else ""
            self.pipeline = "workflow" if wf else req.mode
            graph, out_node = self._graph(req, p, image_name, mask_name, wf)
            prompt_id = self.comfy.queue(graph)
            start, span = 0.15 + 0.75 * k / n_wf, 0.75 / n_wf
            progress(start, f"Queued in ComfyUI ({self.pipeline}{suffix})", phase="prepare")
            hist = self._wait(prompt_id, graph, wf, start, span, suffix, progress)
            results.append((label, self.comfy.output_images(hist, out_node)[: max(1, req.variants)]))

        progress(0.92, "Placing the result in PhotoCraft", phase="place")
        orig = self._find_doc(orig, orig_name)
        base = (p.prompt.strip() or req.mode)[:40]
        layer_mask = None
        if has_sel and req.layer_mask == "soft":
            # the same soft mask the model got: the result blends exactly where the model blended it
            layer_mask = imaging.prepare_mask(mask.crop(region.pil()), req.mask_grow, req.mask_blur)
        mode = req.layer_mask if has_sel else "none"
        items = [(label, i, im, len(ims)) for label, ims in results for i, im in enumerate(ims)]
        layers = []
        # last item first: #1 ends up on top, visible and active, the others hidden below it
        for n, g in enumerate(reversed(range(len(items)))):
            label, i, raw, count = items[g]
            im = raw.convert("RGB").resize((region.w, region.h), Image.LANCZOS)
            name = (f"AI {req.mode}" + (f" [{label}]" if label else "") + f": {base} [{p.seed}]"
                    + (f" #{i + 1}" if count > 1 else ""))
            layers.insert(0, self._import(orig, im, region, mode, name, tag, g, first=(n == 0), hidden=(g > 0),
                                          layer_mask=layer_mask))
        if has_sel:
            self._try("select.reselect")  # selection comes back, ready for another generation
        progress(1.0, f"Done (seed {p.seed})", phase="place")
        return {"seed": p.seed, "layers": layers, "region": region.__dict__, "size": [gw, gh], "pipeline": self.pipeline}

    # ---------- ComfyUI ----------

    def _graph(self, req: Request, p, image_name, mask_name, wf: str | None = None):
        if wf:
            tpl = workflows.load_template(wf)
            return workflows.apply_template(tpl, p, image_name, mask_name)
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

    def _export(self, orig: int, tag: str, need_mask: bool) -> tuple[Image.Image, Image.Image | None]:
        pc = self.pc
        pc.execute("image.duplicate", {"name": f"pccomfy-{tag}", "mergedOnly": True})
        try:
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

    def _expand_canvas(self, req: Request) -> None:
        left, top, right, bottom = (max(0, int(v)) for v in req.outpaint)
        if not any((left, top, right, bottom)):
            raise BridgeError("Set how many pixels to expand by (left/top/right/bottom).")
        doc = self.pc.document()
        W0, H0 = doc["width"], doc["height"]
        for amount, size, anchor in ((left, "width", "right"), (right, "width", "left"),
                                     (top, "height", "bottom"), (bottom, "height", "top")):
            if amount:
                params = {"width": 0, "height": 0, "relative": True, "anchor": anchor, "extensionColor": "transparent"}
                params[size] = amount
                self.pc.execute("image.canvasSize", params)
        ov = max(0, int(req.overlap))
        x0 = left + (ov if left else 0)
        y0 = top + (ov if top else 0)
        x1 = left + W0 - (ov if right else 0)
        y1 = top + H0 - (ov if bottom else 0)
        self.pc.execute("select.all")
        if x1 > x0 and y1 > y0:
            # feather only the edge against the original (feathering the whole selection would round the canvas corners)
            self.pc.execute("select.rect", {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0,
                                            "mode": "subtract", "feather": max(0, ov // 2)})

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
