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
    ("multi_edit", "Multi Image Edit"),
    ("upscale", "Upscale (new file)"),
    ("refine", "Refine (same size)"),
    ("img2img", "Image → image"),    # only for a workflow of your own (no model tab)
]
SHORT_MODES = {"txt2img": "Text", "edit": "Edit", "inpaint": "Fill Selection", "outpaint": "Expand", "multi_edit": "Multi Edit",
               "remove": "Remove Selection", "upscale": "Upscale", "refine": "Refine", "img2img": "Img2img"}   # layer names
MODE_TIPS = {      # for a workflow of your own (no model tab); the tabs show the tips of their model (models.Model.mode_tips)
    "inpaint": "Select an area, type what should appear there, then Generate.",
    "remove": "Select the object (whole object inside), then Generate.",
    "multi_edit": "Changes the whole picture from your text and the reference images in the slots. A selection is ignored.",
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


SLOT_ART = {      # 16x16 pixel art ("#" = drawn) for the icons in the reference slots; "paste", "file" and "describe" are drawn in icon_image
    "remove": ["................",
               "................",
               "..##........##..",
               "...##......##...",
               "....##....##....",
               ".....##..##.....",
               "......####......",
               ".......##.......",
               "......####......",
               ".....##..##.....",
               "....##....##....",
               "...##......##...",
               "..##........##..",
               "................",
               "................",
               "................"],
    "cut": ["................",
           ".#..........#...",
           ".##........##...",
           "..##......##....",
           "...##....##.....",
           "....##..##......",
           ".....####.......",
           "......##........",
           ".....####.......",
           "....##..##......",
           "..###....###....",
           ".#..#....#..#...",
           ".#..#....#..#...",
           "..##......##....",
           "................",
           "................"],
}


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
    elif kind in SLOT_ART:                        # the small icons of the reference slots (see SLOT_ART)
        for y, row in enumerate(SLOT_ART[kind]):
            for x, ch in enumerate(row):
                if ch == "#":
                    px[y][x] = color
    elif kind == "paste":                         # clipboard with a clip and two lines of text
        rect(2, 2, 13, 15, fill=False)
        rect(5, 0, 10, 3)
        rect(5, 7, 10, 7)
        rect(5, 10, 10, 10)
    elif kind == "file":                          # a sheet with a plus: add a file
        rect(1, 0, 10, 15, fill=False)
        rect(3, 8, 8, 8)
        rect(5, 6, 5, 10)
        rect(11, 11, 15, 11)
        rect(13, 9, 13, 13)
    elif kind == "describe":                      # lines of text
        rect(1, 2, 14, 2)
        rect(1, 5, 11, 5)
        rect(1, 8, 14, 8)
        rect(1, 11, 8, 11)
        rect(1, 14, 12, 14)
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


def conn_status(parent, name: str = "ComfyUI"):
    """'ComfyUI' and a dot after it (footer and settings window): returns (frame, dot); set_dot colours the dot."""
    f = ttk.Frame(parent)
    ttk.Label(f, text=name, style="Muted.TLabel").pack(side="left")
    dot = ttk.Label(f, text="●", style="ConnWait.TLabel")
    dot.pack(side="left", padx=(3, 0))
    return f, dot


def set_dot(dot, ok: bool | None):
    """Green = connected, red = not connected, grey = not known yet (before the first refresh)."""
    dot.configure(style="ConnOk.TLabel" if ok else "ConnWait.TLabel" if ok is None else "ConnBad.TLabel")


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


class ThinScrollbar:
    """A very thin vertical scroll bar for a Canvas: a narrow strip with a rounded handle, no arrows. Dragging the handle,
    a click on the strip and the mouse wheel scroll; the handle lightens under the mouse. Shown only while it is needed
    (`show` / `hide`)."""

    THUMB, THUMB_HOT = "#808080", "#b0b0b0"      # visible on the window grey (#535353) without standing out

    def __init__(self, parent, canvas, width: int, bg: str):
        self.canvas, self.width = canvas, width
        self.bar = tk.Canvas(parent, width=width, height=1, bg=bg, highlightthickness=0, bd=0, cursor="arrow")   # height: from the canvas beside it
        self.shown = False
        self._first, self._last, self._drag, self._hot = 0.0, 1.0, None, False
        canvas.configure(yscrollcommand=self.set)
        self.bar.bind("<Configure>", lambda e: self._draw())
        self.bar.bind("<Enter>", lambda e: self._heat(True))
        self.bar.bind("<Leave>", lambda e: self._heat(False))
        self.bar.bind("<ButtonPress-1>", self._press)
        self.bar.bind("<B1-Motion>", self._move)
        self.bar.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))

    def show(self):
        if not self.shown:
            self.shown = True
            self.bar.pack(side="right", fill="y", before=self.canvas)

    def hide(self):
        if self.shown:
            self.shown = False
            self.bar.pack_forget()
            self.canvas.yview_moveto(0)

    def set(self, first, last):
        self._first, self._last = float(first), float(last)
        self._draw()

    def _heat(self, hot: bool):
        self._hot = hot
        self._draw()

    def _draw(self):
        b = self.bar
        try:
            h = b.winfo_height()
            b.delete("all")
        except tk.TclError:
            return
        if not isinstance(h, int) or h <= 1 or self._last - self._first >= 1.0:
            return
        w = self.width
        y0 = max(0, round(self._first * h))
        y1 = min(h, max(y0 + 2 * w, round(self._last * h)))
        r, c = w / 2, (self.THUMB_HOT if (self._hot or self._drag is not None) else self.THUMB)
        b.create_oval(1, y0, w - 1, y0 + w, fill=c, outline=c)             # round ends
        b.create_oval(1, y1 - w, w - 1, y1, fill=c, outline=c)
        b.create_rectangle(1, y0 + r, w - 1, y1 - r, fill=c, outline=c)

    def _press(self, e):
        h = max(1, self.bar.winfo_height())
        f = e.y / h
        if self._first <= f <= self._last:
            self._drag = (e.y, self._first)                   # grab the handle where it was hit
        else:
            self.canvas.yview_moveto(f - (self._last - self._first) / 2)    # a click on the strip: jump there
        self._draw()

    def _move(self, e):
        if self._drag is not None:
            y, first = self._drag
            self.canvas.yview_moveto(first + (e.y - y) / max(1, self.bar.winfo_height()))

    def wheel(self, e):
        """Mouse wheel anywhere over the scrolled area (not over a text field or a list, which scroll themselves)."""
        if not self.shown:
            return
        try:
            if e.widget.winfo_class() in ("Text", "Listbox", "TCombobox", "ComboboxPopdownFrame"):
                return
        except Exception:
            pass
        self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")


class Slider(tk.Canvas):
    """A slider in PhotoCraft's look: a thin track, light up to the value and dark after it, and a round white knob (drawn
    smooth with Pillow; Tk's own ovals are jagged). It stands in for ttk.Scale: from_, to, variable, command, length and
    configure(state=...). A click on the track jumps there, dragging follows the mouse; greyed out it is grey and ignores
    the mouse."""

    TRACK, KNOB = 4, 14                              # px before the display scaling
    FILL, REST = "#e6e6e6", "#2a2a2a"                # the track up to the value / after it
    FILL_OFF, KNOB_OFF = "#6a6a6a", "#9a9a9a"        # greyed out
    _knobs: dict = {}                                # (colour, size) -> PhotoImage, shared by all sliders

    def __init__(self, parent, from_=0.0, to=1.0, variable=None, command=None, length=None, scale: float = 1.0, **kw):
        self._s = scale
        self._lo, self._hi, self._var, self._cmd = float(from_), float(to), variable, command
        try:
            bg = ttk.Style().lookup("TFrame", "background") or BG
        except Exception:
            bg = BG
        super().__init__(parent, height=round(self.KNOB * scale) + 2, width=length or round(120 * scale), bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2", **kw)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._click)
        self.bind("<B1-Motion>", self._click)
        if variable is not None:
            try:
                variable.trace_add("write", lambda *a: self._draw())    # the knob follows presets, resets, loaded state
            except Exception:
                pass
        self._draw()

    def configure(self, cnf=None, **kw):
        out = super().configure(cnf, **kw)
        if cnf or kw:
            self._draw()
        return out

    config = configure

    def _on(self) -> bool:
        return str(self.cget("state")) != "disabled"

    def _value(self) -> float:
        try:
            return min(self._hi, max(self._lo, float(self._var.get())))
        except (TypeError, ValueError, AttributeError, tk.TclError):
            return self._lo

    def _ends(self):
        w = self.winfo_width()
        if not isinstance(w, int) or w <= 1:
            try:
                w = int(self.cget("width"))
            except (TypeError, ValueError):
                w = 120
        r = self.KNOB * self._s / 2
        return r + 1, max(r + 2, w - r - 1)

    def _knob(self, colour: str, d: int):
        if (colour, d) not in self._knobs:
            from PIL import Image, ImageDraw
            n = d * 8
            im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse([4, 4, n - 5, n - 5], fill=colour, outline="#3a3a3a", width=6)
            import base64
            import io
            buf = io.BytesIO()
            im.resize((d, d), Image.LANCZOS).save(buf, "PNG")
            self._knobs[(colour, d)] = tk.PhotoImage(master=self, data=base64.b64encode(buf.getvalue()).decode("ascii"))
        return self._knobs[(colour, d)]

    def _draw(self):
        try:
            self.delete("all")
            x0, x1 = self._ends()
            h = self.winfo_height()
            cy = (h if isinstance(h, int) and h > 1 else round(self.KNOB * self._s) + 2) / 2
            on, t = self._on(), max(2, round(self.TRACK * self._s))
            xv = x0 + (self._value() - self._lo) / ((self._hi - self._lo) or 1) * (x1 - x0)
            self.create_line(x0, cy, x1, cy, fill=self.REST, width=t, capstyle="round")
            if xv > x0:
                self.create_line(x0, cy, xv, cy, fill=self.FILL if on else self.FILL_OFF, width=t, capstyle="round")
            self.create_image(xv, cy, image=self._knob("#ffffff" if on else self.KNOB_OFF, round(self.KNOB * self._s)))
        except (tk.TclError, ImportError, OSError):
            pass

    def _click(self, e):
        if not self._on():
            return "break"
        x0, x1 = self._ends()
        v = self._lo + min(1.0, max(0.0, (e.x - x0) / ((x1 - x0) or 1))) * (self._hi - self._lo)
        if self._var is not None:
            self._var.set(v)
        self._draw()
        if self._cmd:
            self._cmd(str(v))        # as ttk.Scale does: the new value as text
        return "break"


VALUE_W = 9        # characters of a slider's value box: "hard edge" fits, so every slider row has the same length

ENHANCE_TIP = "On: a text model writes the detailed prompt from your short text. Off: your text is sent as typed."
LORA_TIP = "The workflow's own LoRA: on/off, and its strength."
STAGE_TIP = "A stage of the workflow you can switch off."
FONT = "Segoe UI" if os.name == "nt" else "Sans"
CLIP_DEFAULT = "(workflow default)"


def preset_stem(name: str) -> str:
    """File-name-safe preset name."""
    return re.sub(r"[^\w .\-]", "_", name.strip(), flags=re.UNICODE).strip(". ") or "preset"

BG, PANEL, FG, MUTED, ACCENT = "#535353", "#282828", "#eeeeee", "#cfcfcf", "#f28c28"   # PhotoCraft grey (measured from a screenshot), orange accent; PANEL = inactive tab, fields, buttons, slots
NA_RED = "#ff6b6b"      # text of a tab that is not available (model files missing); 5.3 : 1 on PANEL
DISABLED = "#8e8e8e"   # text of a greyed-out control: clearly darker than MUTED, so it reads as "not available here"
SCALE_MODES = ("upscale", "refine")   # these run only with an upscale workflow (a node titled pc:upscale)
ERROR, ERROR_TEXT = "#e5484d", "#ffc2c2"
DONE_GREEN = "#39A95D"      # only the word "Done" above the bar
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
    "ThinScrollbar",
    "Slider",
    "VALUE_W",
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
    "SLOT_ART",
    "Tooltip",
    "ENHANCE_TIP",
    "LORA_TIP",
    "STAGE_TIP",
    "FONT",
    "CLIP_DEFAULT",
    "preset_stem",
    "BG",
    "PANEL",
    "NA_RED",
    "FG",
    "MUTED",
    "ACCENT",
    "DISABLED",
    "SCALE_MODES",
    "ERROR",
    "ERROR_TEXT",
    "DONE_GREEN",
    "conn_status",
    "set_dot",
    "_dpi_aware",
    "duration_text",
    "scale_text",
    "parse_list",
    "sweep_requests",
    "MIN_W",
]
