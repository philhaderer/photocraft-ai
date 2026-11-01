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
from . import fonts, models, winlink
from .bridge import Bridge, BridgeError, Request, mask_is_used, prompt_phase_nodes
from .comfy import Cancelled, ComfyError, ComfyUI
from .photocraft import PhotoCraft, PhotoCraftError
from .workflows import _tags as workflows_tags
from .workflows import FLUX2_SCHEDULER, GenParams, has_upscale_slot, list_templates, load_template, bypass_lora, lora_strength, lora_switches, lora_tip, resolve, sampler_values, stage_info, stage_switches, writer_model, writer_name

FILL_CONTEXT = 0.2   # Context (margin) that Fill Selection starts with

MODE_LABELS = [
    ("txt2img", "Text to image"),
    ("outpaint", "Expand image"),
    ("inpaint", "Fill Selection"),
    ("remove", "Remove Selection"),
    ("edit", "Edit Canvas"),
    ("multi_edit", "Multi Image Edit"),
    ("upscale", "Upscale (new file)"),
    ("refine", "Refine (same size)"),
    ("img2img", "Image → image"),    # only for a workflow of your own (no model tab)
]
SHORT_MODES = {"txt2img": "Text", "edit": "Edit", "inpaint": "Fill Selection", "outpaint": "Expand", "multi_edit": "Multi Edit",
               "remove": "Remove Selection", "upscale": "Upscale", "refine": "Refine", "img2img": "Img2img"}   # layer names
MODE_TIPS = models.FUNCTION_TIPS    # the tooltips of the function buttons, the same for every model (user 28.10.)
EXPAND_HINT = "Try removing the prompt for expanding"
BUILTIN = "Built-in (checkpoint)"
PROMPT_LINES = 5     # height of the prompt field in lines (it can be dragged taller or smaller)
LAYER_MASKS = {"soft": "soft", "selection": "hard (from selection)", "none": "none"}
# "auto" left the menu (28.10., the user's choice: each model's function starts with its own value); a preset or saved
# state that still says "auto" opens as soft


def layer_mask_key(shown_or_key: str) -> str:
    """The layer mask's key ("soft", "selection", "none") from what the menu shows or what was saved."""
    if shown_or_key in LAYER_MASKS:
        return shown_or_key
    return {v: k for k, v in LAYER_MASKS.items()}.get(shown_or_key, "soft")

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
                 relief="solid", borderwidth=1, padx=6, pady=4, font=font(9)).pack()

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
    (`show` / `hide`; with `auto`, by itself whenever the content is longer than the view, e.g. the prompt field).
    Works for any widget that scrolls like a Canvas (a Text too)."""

    THUMB, THUMB_HOT = "#808080", "#b0b0b0"      # visible on the window grey (#535353) without standing out

    def __init__(self, parent, canvas, width: int, bg: str, auto: bool = False):
        self.canvas, self.width, self.auto = canvas, width, auto
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
        if self.auto:
            if self._last - self._first < 1.0:
                self.show()
            elif self.shown:
                self.shown = False          # not hide(): that scrolls to the top, the view is whole anyway
                self.bar.pack_forget()
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
            if e.widget.winfo_toplevel() is not self.canvas.winfo_toplevel():    # another window (the settings) scrolls itself
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
    FILL, REST = "#e6e6e6", "#686868"                # the track up to the value / after it (PhotoCraft's grey)
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
        box = vars(self).get("box")          # its value box (ValueBox) is greyed out with it
        if box is not None and "state" in kw:
            box.configure(state=kw["state"])
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
SLIDER_W = 140     # px (before the display scaling) of every slider: all of them sit in one column on the right


def parse_number(text: str) -> "float | None":
    """A typed number: comma or point as the decimal sign ("0,2" = 0.2), a unit or spaces around it ignored
    ("35 %"); None when there is no number in it."""
    raw = "".join(c for c in str(text).replace(",", ".") if c in "0123456789.-")
    try:
        return float(raw)
    except ValueError:
        return None


def number_typed_ok(action: str, typed: str, after: str) -> bool:
    """Key check of a number field (Tk's %d, %S, %P): digits and one decimal point or comma can be typed; deleting is
    always fine (live bug 28.10.: the check also ran on deleting, so "%", the space and "hard edge" could not be
    deleted)."""
    if action != "1":
        return True
    if any(c not in "0123456789.," for c in typed):
        return False
    return sum(after.count(c) for c in ".,") <= 1


def steps_typed_ok(action: str, typed: str, after: str) -> bool:
    """Steps: whole numbers of at most two digits (user 1.11.)."""
    return action != "1" or (typed.isdigit() and len(after) <= 2 and after.isdigit())


def cfg_typed_ok(action: str, typed: str, after: str) -> bool:
    """CFG: 0 to 9.9: one digit, and after a point or comma one more digit (user 1.11.)."""
    if action != "1":
        return True
    return all(c in "0123456789.," for c in typed) and re.fullmatch(r"\d?([.,]\d?)?", after) is not None


SEED_DIGITS = 8


def seed_typed_ok(action: str, typed: str, after: str) -> bool:
    """Seed: whole numbers of at most 8 digits; -1 (random) can be typed too (user 1.11.)."""
    return action != "1" or (all(c in "0123456789-" for c in typed) and re.fullmatch(r"-?\d{0,%d}" % SEED_DIGITS, after) is not None)


class SelectableLabel(tk.Text):
    """A wrapped text that looks like a label but can be selected with the mouse and copied (Ctrl+C): the tips under the
    prompt (user 1.11.). `configure(text=...)` sets the text; the height follows the wrapped lines."""

    def __init__(self, parent, text: str = "", fg: str = "", bg: str = "", fnt=None):
        super().__init__(parent, height=1, width=1, wrap="word", bd=0, highlightthickness=0, padx=0, pady=0, bg=bg, fg=fg,
                         font=fnt, cursor="xterm", insertwidth=0, takefocus=0, selectbackground="#5a6678", inactiveselectbackground="#5a6678")
        self.bind("<Button-1>", lambda e: self.focus_set(), add="+")      # a disabled Text does not take the focus itself
        self.bind("<Configure>", lambda e: self._fit(), add="+")
        self.configure(text=text)

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            t = kw.pop("text")
            super().configure(state="normal")
            self.delete("1.0", "end")
            self.insert("1.0", t)
            super().configure(state="disabled")
            self.after_idle(self._fit)
            if not (cnf or kw):
                return None
        return super().configure(cnf, **kw)

    config = configure

    def _fit(self):
        try:
            if self.winfo_width() < 20:          # not shown yet: the width is unknown, a Configure comes when it is
                return
            n = self.tk.call(self._w, "count", "-displaylines", "1.0", "end")
            n = int(n[0] if isinstance(n, (tuple, list)) else n)
            if n >= 1 and int(self.cget("height")) != n:
                super().configure(height=n)
        except (tk.TclError, TypeError, ValueError):
            pass


class ValueBox(ttk.Entry):
    """The value of a slider in a small dark box on its right (as in PhotoCraft), and you can type into it: Enter or
    leaving the box takes the number, kept inside the slider's range (only digits and one decimal point or comma can be
    typed). The unit stays while you type (else the number shifts, user 28.10.): a click puts the cursor where you
    clicked, a double-click or Tab selects the number without the unit, Up/Down step the value (0.05 for a 0..1 value,
    1 for %, or `step` in shown units).
    `factor`: shown = value * factor (100 for the % sliders). `command` shows the value in its format, as after a drag.
    configure(text=...) shows a value, as the label it stands in for did."""

    def __init__(self, parent, slider, command, factor: float = 1.0, step: float | None = None):
        self._text = tk.StringVar(value="")
        super().__init__(parent, textvariable=self._text, width=VALUE_W, style="Value.TEntry", justify="center", font=font(9))
        self._slider, self._cmd, self._factor, self._shown_step = slider, command, factor, step
        self._clicked = False
        slider.box = self
        for ev in ("<Return>", "<KP_Enter>", "<FocusOut>"):
            self.bind(ev, self._commit)
        self.bind("<ButtonPress-1>", self._press, add="+")
        self.bind("<FocusIn>", lambda e: self.after_idle(self._start_edit))
        self.bind("<Double-Button-1>", self._select_number)
        self.bind("<Up>", lambda e: self._step(1))
        self.bind("<Down>", lambda e: self._step(-1))
        try:
            self.configure(validate="key", validatecommand=(self.register(number_typed_ok), "%d", "%S", "%P"))
        except (AttributeError, tk.TclError):
            pass
        self.bind("<Escape>", lambda e: self._cmd())

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self._text.set(kw.pop("text"))
            if not (cnf or kw):
                return None
        return super().configure(cnf, **kw)

    config = configure

    def cget(self, key):
        return self._text.get() if key == "text" else super().cget(key)

    def _select_all(self):
        try:
            self.selection_range(0, "end")
            self.icursor("end")
        except tk.TclError:
            pass

    _typed_ok = staticmethod(number_typed_ok)

    @staticmethod
    def _number_span(text: str) -> tuple:
        """Where the number stands in the shown text ("30 %" -> 0, 2); the whole text when there is none."""
        idx = [i for i, c in enumerate(text) if c in "0123456789.,-"]
        return (idx[0], idx[-1] + 1) if idx else (0, len(text))

    def _select_number_part(self):
        a, b = self._number_span(self._text.get())
        try:
            self.selection_range(a, b)
            self.icursor(b)
        except tk.TclError:
            pass

    def _press(self, _e=None):
        self._clicked = True         # Tk's own binding puts the cursor where you clicked

    def _start_edit(self):
        """Tab into the box selects the number (typing replaces it, the unit stays); a click keeps the cursor."""
        clicked, self._clicked = self._clicked, False
        if not clicked:
            self._select_number_part()

    def _select_number(self, _e=None):
        """Double-click: the whole number (Tk's word selection stops at the decimal point), never the unit."""
        self._select_number_part()
        return "break"

    def _typed_value(self) -> "float | None":
        t = self._text.get().strip().lower()
        v = parse_number(t)
        if v is None and t.startswith("hard"):
            v = 0.0
        return None if v is None else v / self._factor

    def _step(self, sign: int):
        """Up/Down: one step up or down, from what is typed (else the slider's value), kept in range."""
        s = self._slider
        if s._var is None or not s._on():
            return "break"
        shown_step = self._shown_step or (1.0 if (self._factor != 1 or s._hi > 1.5) else 0.05)
        step = shown_step / self._factor
        v = self._typed_value()
        v = s._value() if v is None else v
        v = round(round(v / step) * step + sign * step, 6)
        s._var.set(min(s._hi, max(s._lo, v)))
        s._draw()
        self._cmd()
        self._select_number_part()          # still in the box: the number selected, the unit stays
        return "break"

    def _commit(self, _e=None):
        s = self._slider
        v = self._typed_value()
        if v is not None and s._var is not None and s._on():
            s._var.set(min(s._hi, max(s._lo, v)))
            s._draw()
        self._cmd()

ENHANCE_TIP = "On: a text model writes the detailed prompt from your short text. Off: your text is sent as typed."
LORA_TIP = "The workflow's own LoRA: on/off, and its strength."
STAGE_TIP = "A stage of the workflow you can switch off."
FONT = "Inter" if fonts.load() else ("Segoe UI" if os.name == "nt" else "Sans")   # Inter = PhotoCraft's font (fonts.py)


def font(size: int, bold: bool = False) -> tuple:
    """A Tk font at `size` pt (the Segoe UI size the layout was made for). Inter runs about 8 % wider, so it is set one
    point smaller (9 pt -> 8 pt: 11 instead of 12 px at 100 %) and keeps the texts as wide as before; its bold is the
    SemiBold file (only Regular and SemiBold are shipped)."""
    if FONT == "Inter":
        return ("Inter SemiBold" if bold else "Inter", size - 1)
    return (FONT, size, "bold") if bold else (FONT, size)
CLIP_DEFAULT = "(workflow default)"



PAGE_NOT_SAVED = ("mode", "workflow", "clip", "checkpoint", "seed", "prompt", "negative", "variants")   # what "Set as my settings" leaves out: the page itself, the text, the seed and the number of variants
BG, PANEL, FG, MUTED, ACCENT = "#535353", "#282828", "#eeeeee", "#cfcfcf", "#378ef0"   # PhotoCraft grey and blue (both measured from a screenshot); PANEL = inactive tab, fields, buttons, slots
ACCENT_TEXT = "#6aaaf5"     # the blue for text and thin lines on the grey (the exact blue is too dark there: 2.3 : 1 on BG, this 3.2 : 1 like the old orange)
NA_RED = "#ff6b6b"      # text of a tab that is not available (model files missing); 5.3 : 1 on PANEL
DISABLED = "#8e8e8e"   # text of a greyed-out control: clearly darker than MUTED, so it reads as "not available here"
SCALE_MODES = ("upscale", "refine")   # these run only with an upscale workflow (a node titled pc:upscale)
NO_LLM_MODES = ("outpaint", "remove") + SCALE_MODES   # no "LLM prompt enhancement" row: fixed or ready-made prompts (user 30.10.)
LLM_TIP = ("Describes the picture in PhotoCraft (all visible layers) in one or two sentences, using the text model of the chosen "
           "model, and adds the description to the end of the prompt. Ctrl+Z in the prompt takes it away again.")
STYLES_TIP = "Style prompts"
STD_WORKFLOW = "flux3-klein-upscale-std.json"      # Flux 3 Upscale without AusBoss' nodes (test A2)
V10_WORKFLOW = "moss-image-inpaint-v10.json"      # MOSS Fill / Expand as published (MOSS Inpainting v10), test switch next to Prompt
V10_TIP = ("Test: runs MOSS Inpainting v10 as published instead of the plugin's own cut-out. Its graph crops around the selection "
           "(256 px of context), softens the mask and pastes the result back; needs the KJNodes and Essentials packs. "
           "Context and Edge feather do not apply. Off: the plugin cuts out the part. Compare the results.")
STD_NODES_TIP = "Test: runs Flux 3 Upscale from ComfyUI's standard nodes instead of the AusBoss nodes. Compare the results."
LIVE_TIP = "Shows the picture while it is being made, under the plugin. It goes away when the result is in PhotoCraft."
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


PREVIEW_MAX_H = 210  # the live preview is at most this high before the display scaling, landscape too (a tall picture gets narrower; user 30.10.: 300 was too high, now 70 %)
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
    "SLIDER_W",
    "ValueBox",
    "parse_number",
    "number_typed_ok",
    "SelectableLabel",
    "steps_typed_ok",
    "cfg_typed_ok",
    "seed_typed_ok",
    "SEED_DIGITS",
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
    "layer_mask_key",
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
    "font",
    "CLIP_DEFAULT",
    "BG",
    "PANEL",
    "NA_RED",
    "FG",
    "MUTED",
    "ACCENT",
    "ACCENT_TEXT",
    "DISABLED",
    "SCALE_MODES",
    "NO_LLM_MODES",
    "LIVE_TIP",
    "LLM_TIP",
    "STYLES_TIP",
    "STD_WORKFLOW",
    "STD_NODES_TIP",
    "V10_WORKFLOW",
    "V10_TIP",
    "PAGE_NOT_SAVED",
    "PREVIEW_MAX_H",
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
