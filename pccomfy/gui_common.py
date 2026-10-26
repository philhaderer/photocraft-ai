"""Small bridge window (tkinter). Sits next to PhotoCraft: select in PhotoCraft, type the prompt here."""

from __future__ import annotations

import json
import os
import queue
import random
import re
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import config as cfgmod
from . import models, winlink
from .bridge import Bridge, BridgeError, Request, mask_is_used, prompt_phase_nodes
from .comfy import Cancelled, ComfyError, ComfyUI
from .photocraft import PhotoCraft, PhotoCraftError
from .workflows import _tags as workflows_tags
from .workflows import FLUX2_SCHEDULER, GenParams, has_upscale_slot, list_templates, load_template, bypass_lora, lora_strength, lora_switches, lora_tip, resolve, sampler_values, stage_info, stage_switches, writer_model, writer_name

FILL_CONTEXT = 0.2   # Context (margin) that Fill Selection starts with

MODE_LABELS = [
    ("txt2img", "Text to image"),
    ("edit", "Edit whole image"),
    ("inpaint", "Fill Selection"),
    ("remove", "Remove Selection"),
    ("outpaint", "Expand image"),
    ("reference", "Insert reference image"),
    ("upscale", "Upscale (new file)"),
    ("refine", "Refine (same size)"),
    ("img2img", "Image → image"),    # only for a workflow of your own (no model tab)
]
SHORT_MODES = {"txt2img": "Text", "edit": "Edit", "inpaint": "Fill Selection", "outpaint": "Expand", "reference": "Reference",
               "remove": "Remove Selection", "upscale": "Upscale", "refine": "Refine", "img2img": "Img2img"}   # layer names
MODE_TIPS = {      # for a workflow of your own (no model tab); the tabs show the tips of their model (models.Model.mode_tips)
    "inpaint": "Select an area, type what should appear there, then Generate.",
    "remove": "Select the object (whole object inside), then Generate.",
    "reference": "Put the reference on its own top layer, select where it goes, then Generate.",
    "outpaint": "Extend the canvas with the Crop tool (Enter) and fill the new area white, then Generate.",
    "edit": "Changes the whole picture from your text. A selection is ignored.",
    "img2img": "Reworks the picture (or selection) from your text.",
    "upscale": "Enlarges the picture (or selection) into a NEW document. Needs an upscale workflow.",
    "refine": "Cleans up the picture (or selection) at the same size. Needs an upscale workflow.",
    "txt2img": "New picture from text only, as a new layer. A selection is ignored.",
}
EXPAND_HINT = "Try removing the prompt for expanding"
BUILTIN = "Built-in (checkpoint)"
PROMPT_LINES = 5     # height of the prompt field in lines (it can be dragged taller or smaller)
LAYER_MASKS = {"auto": "auto (recommended)", "soft": "soft", "selection": "hard (from selection)", "none": "none"}

def word_left(before: str) -> int:
    """How many characters Ctrl+Left moves back, as in an editor: over spaces/punctuation/line breaks, then over the word."""
    i = len(before)
    while i > 0 and not before[i - 1].isalnum():
        i -= 1
    while i > 0 and before[i - 1].isalnum():
        i -= 1
    return len(before) - i


def word_right(after: str) -> int:
    """How many characters Ctrl+Right moves on: over the rest of the word, then to the start of the next one."""
    j = 0
    while j < len(after) and after[j].isalnum():
        j += 1
    while j < len(after) and not after[j].isalnum():
        j += 1
    return j


def _arrow_icon(root, kind: str, color: str):
    """Undo / Redo: a smooth U-turn arrow drawn with Pillow (8x supersampled), about 22 px at 100 % scaling, as a PNG PhotoImage."""
    import base64
    import io
    from PIL import Image, ImageDraw, ImageOps
    try:
        ui = max(1.0, float(root.winfo_fpixels("1i")) / 96)
    except Exception:
        ui = 1.0
    px = max(16, round(22 * ui))
    sup = 8
    n = px * sup
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, round(n * 0.105))
    P = lambda x, y: (x * n, y * n)          # noqa: E731  (unit square -> pixels)
    cx, cy, r = 0.60, 0.56, 0.25
    d.arc([P(cx - r, cy - r), P(cx + r, cy + r)], start=270, end=90, fill=color, width=w)
    d.line([P(cx, cy - r), P(0.38, cy - r)], fill=color, width=w)
    d.line([P(cx, cy + r), P(0.34, cy + r)], fill=color, width=w)
    ty = cy - r
    d.polygon([P(0.16, ty), P(0.40, ty - 0.19), P(0.40, ty + 0.19)], fill=color)
    if kind == "redo":
        im = ImageOps.mirror(im)
    buf = io.BytesIO()
    im.resize((px, px), Image.LANCZOS).save(buf, "PNG")
    return tk.PhotoImage(master=root, data=base64.b64encode(buf.getvalue()).decode("ascii"))


def icon_image(root, kind: str, color: str):
    """A 16x16 icon for a button, drawn pixel by pixel: "save" (floppy disk), "saveas" (floppy with a plus), "trash"."""
    if kind in ("undo", "redo"):
        try:
            return _arrow_icon(root, kind, color)
        except Exception:
            pass                     # no Pillow / PNG support: the pixel art below
    n = 16
    px = [[None] * n for _ in range(n)]

    def rect(x0, y0, x1, y1, fill=True, c=color):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if fill or x in (x0, x1) or y in (y0, y1):
                    px[y][x] = c

    ART = {"undo": ["................",
                    "................",
                    "....#...........",
                    "...##...........",
                    "..###..######...",
                    ".####.#######...",
                    "..###.##....###.",
                    "...##.#......##.",
                    "....#........##.",
                    "..............##",
                    ".............###",
                    "...........####.",
                    "......#####.....",
                    "................",
                    "................",
                    "................"]}
    ART["redo"] = [row[::-1] for row in ART["undo"]]
    if kind in ART:
        for y, row in enumerate(ART[kind]):
            for x, ch in enumerate(row):
                if ch == "#":
                    px[y][x] = color
    elif kind == "copy":                          # two sheets
        rect(0, 0, 9, 11, fill=False)
        rect(5, 4, 14, 15, c=BG)
        rect(5, 4, 14, 15, fill=False)
        rect(7, 7, 12, 7)
        rect(7, 10, 12, 10)
    elif kind in ("save", "saveas"):
        rect(0, 0, 13, 13, fill=False)          # the disk
        rect(3, 0, 10, 4)                        # the shutter
        rect(2, 8, 11, 13, fill=False)           # the label
        if kind == "saveas":
            rect(11, 8, 15, 15, c=BG)            # room for the plus
            rect(13, 9, 13, 15, c="#6fcf97")
            rect(10, 12, 15, 12, c="#6fcf97")
    else:                                         # trash can
        rect(5, 0, 10, 1)                         # handle
        rect(1, 2, 14, 3)                         # lid
        rect(3, 4, 12, 15, fill=False)            # body
        for x in (6, 9):
            rect(x, 6, x, 13)
    img = tk.PhotoImage(master=root, width=n, height=n)
    for y, row in enumerate(px):
        for x, c in enumerate(row):
            if c:
                img.put(c, (x, y))
    return img


class Tooltip:
    """Small hover tooltip for any tk/ttk widget."""

    def __init__(self, widget, text: str, delay: int = 450):
        self.widget, self.text, self.delay, self.tip, self._job = widget, text, delay, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._hide()
        self._job = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tip or not self.text:
            return
        x, y = self.widget.winfo_rootx() + 12, self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", wraplength=340, background="#ffffe0", foreground="#000000",
                 relief="solid", borderwidth=1, padx=6, pady=4, font=("Segoe UI" if os.name == "nt" else "Sans", 9)).pack()

    def _hide(self, _e=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


ENHANCE_TIP = "On: a text model writes the detailed prompt from your short text. Off: your text is sent as typed."
LORA_TIP = "The workflow's own LoRA: on/off, and its strength."
STAGE_TIP = "A stage of the workflow you can switch off."
FONT = "Segoe UI" if os.name == "nt" else "Sans"
CLIP_DEFAULT = "(workflow default)"


def preset_stem(name: str) -> str:
    """File-name-safe preset name."""
    return re.sub(r"[^\w .\-]", "_", name.strip(), flags=re.UNICODE).strip(". ") or "preset"

BG, PANEL, FG, MUTED, ACCENT = "#535353", "#404040", "#eeeeee", "#cfcfcf", "#f28c28"   # PhotoCraft grey (measured from a screenshot), orange accent
DISABLED = "#8e8e8e"   # text of a greyed-out control: clearly darker than MUTED, so it reads as "not available here"
REF_STYLES = {"classic": "Classic: subject first, long instruction", "simple": "Simple: picture first, one short sentence"}
SCALE_MODES = ("upscale", "refine")   # these run only with an upscale workflow (a node titled pc:upscale)
ERROR, ERROR_TEXT = "#e5484d", "#ffc2c2"
def _dpi_aware() -> None:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # system DPI aware (Windows 8.1+)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def duration_text(seconds: float) -> str:
    """"23 s", "1 min 05 s"."""
    s = max(0, round(seconds))
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60:02d} s"


def scale_text(v) -> str:
    """The upscale factor as the drop-down shows it: "x 1.5", "x 2"."""
    try:
        return "x " + f"{float(v):g}"
    except (TypeError, ValueError):
        return "x 2"


def parse_list(text: str, cast) -> list:
    """"1024, 1224 1536" -> [1024, 1224, 1536]; whatever is not a number is skipped."""
    out = []
    for part in str(text).replace(";", ",").replace(" ", ",").split(","):
        try:
            if part.strip():
                out.append(cast(part.strip().replace(",", ".")))
        except ValueError:
            pass
    return out


def sweep_requests(req: Request, res_list: list, ctx_list: list) -> list[Request]:
    """The runs of a comparison: the same request (and the same seed) once per base res / context value."""
    import dataclasses
    runs = []
    for rs in res_list or [None]:
        for cx in ctx_list or [None]:
            parts = ([f"res {rs}"] if rs else []) + ([f"ctx {cx:g}"] if cx is not None else [])
            runs.append(dataclasses.replace(req, base_res=rs or req.base_res, context=cx if cx is not None else req.context,
                                            label=" ".join(parts)))
    return runs


MIN_W = 380  # the window's fixed width (it cannot be resized; the height follows the content)


__all__ = [
    "json",
    "os",
    "queue",
    "random",
    "re",
    "threading",
    "time",
    "tk",
    "datetime",
    "Path",
    "messagebox",
    "simpledialog",
    "ttk",
    "cfgmod",
    "models",
    "winlink",
    "Bridge",
    "BridgeError",
    "Request",
    "mask_is_used",
    "prompt_phase_nodes",
    "Cancelled",
    "ComfyError",
    "ComfyUI",
    "PhotoCraft",
    "PhotoCraftError",
    "workflows_tags",
    "FLUX2_SCHEDULER",
    "GenParams",
    "has_upscale_slot",
    "list_templates",
    "load_template",
    "bypass_lora",
    "lora_strength",
    "lora_switches",
    "lora_tip",
    "resolve",
    "sampler_values",
    "stage_info",
    "stage_switches",
    "writer_model",
    "writer_name",
    "FILL_CONTEXT",
    "MODE_LABELS",
    "SHORT_MODES",
    "MODE_TIPS",
    "EXPAND_HINT",
    "BUILTIN",
    "PROMPT_LINES",
    "LAYER_MASKS",
    "word_left",
    "word_right",
    "_arrow_icon",
    "icon_image",
    "Tooltip",
    "ENHANCE_TIP",
    "LORA_TIP",
    "STAGE_TIP",
    "FONT",
    "CLIP_DEFAULT",
    "preset_stem",
    "BG",
    "PANEL",
    "FG",
    "MUTED",
    "ACCENT",
    "DISABLED",
    "REF_STYLES",
    "SCALE_MODES",
    "ERROR",
    "ERROR_TEXT",
    "_dpi_aware",
    "duration_text",
    "scale_text",
    "parse_list",
    "sweep_requests",
    "MIN_W",
]
