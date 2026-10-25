"""Small bridge window (tkinter). Sits next to PhotoCraft: select in PhotoCraft, type the prompt here."""

from __future__ import annotations

import json
import os
import queue
import random
import re
import threading
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
from .workflows import GenParams, has_upscale_slot, list_templates, load_template, bypass_lora, lora_strength, lora_switches, lora_tip, resolve, sampler_values, stage_info, stage_switches, writer_model, writer_name

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


DESC_POS = {"front": "in front of the prompt", "after": "after the prompt"}


def desc_mp_text(v) -> str:
    """The analysis size as the drop-down shows it: "0.5 MP", "full size" (0)."""
    try:
        return "full size" if float(v) <= 0 else f"{float(v):g} MP"
    except (TypeError, ValueError):
        return "0.5 MP"


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


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.state = cfgmod.load_state()
        d = cfg["defaults"]
        pcc, cc = cfg["photocraft"], cfg["comfyui"]
        self.pc = PhotoCraft(pcc["host"], int(pcc["port"]), token_file=pcc["token_file"], headless=bool(pcc["headless"]))
        self.comfy = ComfyUI(cc["url"])
        self.bridge = Bridge(self.pc, self.comfy, pcc["exchange_dir"])
        self.workflows_dir = Path(cc["workflows_dir"]).expanduser()
        self.presets_dir = cfgmod.PRESETS_DIR
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None

        _dpi_aware()   # without it Windows stretches the window as a bitmap on a scaled display: blurry text
        self.root = tk.Tk()
        self.root.title("PhotoCraft × ComfyUI")
        self.root.configure(bg=BG)
        try:
            self.ui = max(1.0, float(self.root.winfo_fpixels("1i")) / 96)   # display scaling (150 % = 1.5)
        except Exception:
            self.ui = 1.0
        self.root.resizable(False, False)       # a fixed width; the height is set from the content (_fit_height)
        self._sized = False
        self._style()
        self._scale_clicks()
        self.root.after(200, lambda: winlink.caption(self.root, (0x40, 0x40, 0x40), (0xee, 0xee, 0xee)))

        g = lambda k, default: self.state.get(k, default)  # noqa: E731
        self.v_mode = tk.StringVar(value=g("mode", "inpaint"))
        self.v_workflow = tk.StringVar(value=g("workflow", BUILTIN))
        self.v_ckpt = tk.StringVar(value=g("checkpoint", d["checkpoint"]))
        self.v_preset = tk.StringVar(value=g("preset", ""))
        self.v_clip = tk.StringVar(value=g("clip", "") or CLIP_DEFAULT)
        self.v_steps = tk.IntVar(value=g("steps", d["steps"]))
        self.v_cfg = tk.DoubleVar(value=g("cfg", d["cfg"]))
        self.v_denoise = tk.DoubleVar(value=g("denoise", d["denoise"]))
        self.v_seed = tk.IntVar(value=-1)
        self.v_variants = tk.IntVar(value=g("variants", d["variants"]))
        self.v_sampler = tk.StringVar(value=g("sampler", d["sampler"]))
        self.v_scheduler = tk.StringVar(value=g("scheduler", d["scheduler"]))
        self.v_res = tk.IntVar(value=g("base_res", d["base_res"]))
        self.v_context = tk.DoubleVar(value=g("context", d["context"]))
        # Context is remembered per mode. Fill Selection starts at 0.2: with a wide margin Fibo lets the new object grow
        # beyond the selection or doubles it (live test); the other modes keep the global default.
        self._ctx_default = d["context"]
        self._ctx_mode = self.v_mode.get()
        self._ctx = {"inpaint": FILL_CONTEXT}
        if self._ctx_mode == "inpaint":
            if abs(self.v_context.get() - self._ctx_default) < 1e-9:   # the old default, never chosen on purpose
                self.v_context.set(FILL_CONTEXT)
        else:
            self._ctx["inpaint"] = FILL_CONTEXT
        self.v_grow = tk.IntVar(value=g("mask_grow", d["mask_grow"]))
        self.v_blur = tk.IntVar(value=g("mask_blur", d["mask_blur"]))
        self.v_overlap = tk.IntVar(value=g("overlap", d["overlap"]))
        self.v_scale = tk.StringVar(value=scale_text(g("scale", 1.5)))
        self.v_top = tk.BooleanVar(value=True)      # the window always belongs to PhotoCraft (no switch any more)
        self.v_feather = tk.DoubleVar(value=g("feather_pct", 2.0))
        self.v_fooocus = tk.BooleanVar(value=g("fooocus", True))
        self.v_enhance = tk.BooleanVar(value=g("enhance", True))
        self.v_turbo = tk.BooleanVar(value=g("turbo", True))
        self.v_lora_str = tk.DoubleVar(value=g("lora_strength", 1.0))
        self.v_model = tk.StringVar(value=g("model", ""))   # the tab; "" = a workflow of your own (everything enabled)
        self.v_sharpen = tk.DoubleVar(value=g("sharpen", 0.0))
        self.v_match = tk.DoubleVar(value=g("match", 0.0))
        self.v_cmp_res = tk.StringVar(value="")
        self.v_cmp_ctx = tk.StringVar(value="")
        self.v_stage = tk.BooleanVar(value=g("stage_on", True))
        self.v_stage2 = tk.BooleanVar(value=g("stage2_on", False))
        self.v_stage3 = tk.BooleanVar(value=g("stage3_on", False))
        self._stage_wf = g("workflow", "")   # the workflow the stage checkboxes were last set for
        try:
            sstr = [float(x) for x in g("stage_strengths", [1.0, 1.0, 1.0])][:3]
        except (TypeError, ValueError):
            sstr = []
        self.v_sstr = [tk.DoubleVar(value=(sstr[i] if i < len(sstr) else 1.0)) for i in range(3)]   # strength of a stage that is a LoRA
        self.v_detail = tk.DoubleVar(value=g("detail", 1.0))
        self.v_describe = tk.BooleanVar(value=bool(g("describe", False)))
        self.v_desc_pos = tk.StringVar(value=DESC_POS.get(g("describe_pos", "front"), DESC_POS["front"]))
        self.v_desc_mp = tk.StringVar(value=desc_mp_text(g("describe_mp", 0.5)))
        self._vals_key = None                # (workflow, speed LoRA on) the steps / CFG / denoise fields were last read for
        self._wf_vals: dict = {}
        self._lora_wf = g("workflow", "")   # the workflow the LoRA strength slider was last set for
        self.v_collage = tk.BooleanVar(value=g("ref_collage", True))
        self.v_cutout = tk.BooleanVar(value=g("ref_cutout", True))
        self.v_refstyle = tk.StringVar(value=REF_STYLES.get(g("ref_style", "simple"), REF_STYLES["simple"]))
        self.v_lmask = tk.StringVar(value=LAYER_MASKS.get(g("layer_mask", "auto"), LAYER_MASKS["auto"]))
        self.v_status = tk.StringVar(value="Ready")
        self.v_conn = tk.StringVar(value="")

        self._build(d)
        self._set_loras(self.state.get("loras"))
        self._booting = True    # the saved window state is shown as it was: the model's starting settings are not applied
        self._on_mode()
        self._booting = False
        self._on_top()
        self._fit_height(self._px(MIN_W))
        self._sized = True
        self.root.after(100, self._poll)
        self.root.after(200, self.refresh)
        self.refresh_presets()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.bind("<Destroy>", self._on_destroy, add="+")

    # ---------- UI ----------

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor="#454545",
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, font=(FONT, 10))
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", foreground=MUTED, font=(FONT, 9))
        s.configure("Badge.TLabel", background=ERROR, foreground="white", font=(FONT, 10, "bold"))
        s.configure("Error.TLabel", foreground=ERROR_TEXT)
        s.configure("TLabelframe", background=BG, bordercolor="#454545")
        s.configure("TLabelframe.Label", background=BG, foreground=MUTED)
        s.configure("TRadiobutton", background=BG, foreground=FG)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        for w in ("TRadiobutton", "TCheckbutton"):
            s.map(w, background=[("active", BG)], indicatorbackground=[("selected", ACCENT), ("active", "#5f5f5f")],
                  indicatorforeground=[("selected", "#1b1b1b")])
        s.configure("TButton", background=PANEL, foreground=FG, padding=6)
        s.map("TButton", background=[("active", "#5f5f5f")])
        s.configure("Icon.TButton", padding=(6, 4))
        s.configure("Tab.Toolbutton", background=PANEL, foreground=FG, padding=(4, 5), anchor="center", relief="flat",
                    borderwidth=0, font=(FONT, 10))
        s.map("Tab.Toolbutton", background=[("selected", ACCENT), ("active", "#5f5f5f")],
              foreground=[("selected", "#1b1b1b")])
        s.configure("Link.TButton", background=BG, foreground=MUTED, padding=(0, 2), borderwidth=0, relief="flat")
        s.map("Link.TButton", foreground=[("active", FG)], background=[("active", BG)])
        s.configure("Accent.TButton", background=ACCENT, foreground="#1b1b1b", font=(FONT, 10, "bold"))
        s.map("Accent.TButton", background=[("active", "#ff9d3d"), ("disabled", "#6e6558")])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
        s.configure("TCheckbutton", indicatorbackground=PANEL, indicatorforeground=FG)
        s.configure("TRadiobutton", indicatorbackground=PANEL)
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG, arrowsize=self._px(18))   # up/down arrows 50 % larger
        s.configure("Horizontal.TProgressbar", background=ACCENT)
        s.configure("Grip.TFrame", background="#454545")
        s.configure("Hint.TLabel", foreground=ACCENT)
        s.configure("Sep.TFrame", background="#9a9a9a")
        s.configure("Done.TLabel", foreground=FG, font=(FONT, 10, "bold"))
        # greyed out must be visible on the dark theme (clam keeps nearly the normal text colour)
        for w in ("TCheckbutton", "TRadiobutton", "TLabel"):
            s.map(w, foreground=[("disabled", DISABLED)])
        for w in ("TCheckbutton", "TRadiobutton"):
            s.map(w, indicatorbackground=[("disabled", BG), ("selected", ACCENT), ("active", "#5f5f5f")],
                  indicatorforeground=[("disabled", DISABLED), ("selected", "#1b1b1b")])
        s.map("TSpinbox", foreground=[("disabled", DISABLED)], fieldbackground=[("disabled", BG)],
              arrowcolor=[("disabled", DISABLED)])
        s.map("TCombobox", foreground=[("disabled", DISABLED), ("readonly", FG)], fieldbackground=[("disabled", BG), ("readonly", PANEL)],
              arrowcolor=[("disabled", DISABLED)])
        # the slider is orange while it works, grey when greyed out (the edge feather: orange = active)
        s.configure("Horizontal.TScale", background=ACCENT, troughcolor="#3a3a3a", bordercolor="#454545",
                    lightcolor=ACCENT, darkcolor=ACCENT)
        s.map("Horizontal.TScale", background=[("disabled", "#6a6a6a")], lightcolor=[("disabled", "#6a6a6a")],
              darkcolor=[("disabled", "#6a6a6a")], troughcolor=[("disabled", BG)])
        s.map("TButton", foreground=[("disabled", DISABLED)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)

    def _scale_clicks(self):
        """A click on a slider's trough moves the handle to where it was clicked (Tk's own behaviour steps by a whole page,
        i.e. to the start or end of a short slider), and dragging follows the mouse."""
        def to_click(e):
            w = e.widget
            try:
                if str(w.cget("state")) == "disabled":
                    return "break"
                lo, hi = float(w.cget("from")), float(w.cget("to"))
                x0, x1 = float(w.coords(lo)[0]), float(w.coords(hi)[0])
                if x1 - x0 < 1:
                    return None
                w.set(lo + min(1.0, max(0.0, (e.x - x0) / (x1 - x0))) * (hi - lo))
            except (tk.TclError, ValueError, TypeError, IndexError, AttributeError):
                return None
            return "break"
        try:
            self.root.bind_class("TScale", "<Button-1>", to_click)
            self.root.bind_class("TScale", "<B1-Motion>", to_click)
        except Exception:
            pass

    def _open_on_click(self, cb):
        def post(_e=None):
            try:
                if str(cb.cget("state")) == "disabled":
                    return None
                cb.focus_set()
                cb.tk.call("ttk::combobox::Post", str(cb))
            except Exception:
                return None
            return "break"
        cb.bind("<Button-1>", post)

    def _text(self, parent, height):
        t = tk.Text(parent, height=height, width=10, wrap="word", bg=PANEL, fg=FG, insertbackground=FG,
                    relief="flat", highlightthickness=1, highlightbackground="#454545", highlightcolor=ACCENT,
                    font=(FONT, 10), padx=6, pady=4, undo=True, maxundo=200)
        self._editor_keys(t)
        return t

    def _editor_keys(self, t):
        """Text-editor keys in a prompt field: Ctrl+Left/Right jump by word (Shift selects), Ctrl+Backspace/Delete delete a
        word, Ctrl+A selects all, Ctrl+Z / Ctrl+Y undo and redo. Ctrl+Enter generates and writes no line break."""
        def cursor(extend, idx):
            proc = "tk::TextKeySelect" if extend else "tk::TextSetCursor"
            try:
                t.tk.call(proc, str(t), idx)
            except tk.TclError:
                t.mark_set("insert", idx)
            t.see("insert")
            return "break"

        def jump(direction, extend):
            def h(_e=None):
                if direction < 0:
                    n = word_left(t.get("1.0", "insert"))
                    return cursor(extend, f"insert-{n}c")
                n = word_right(t.get("insert", "end-1c"))
                return cursor(extend, f"insert+{n}c")
            return h

        def kill(direction):
            def h(_e=None):
                if t.tag_ranges("sel"):
                    t.delete("sel.first", "sel.last")
                elif direction < 0:
                    t.delete(f"insert-{word_left(t.get('1.0', 'insert'))}c", "insert")
                else:
                    t.delete("insert", f"insert+{word_right(t.get('insert', 'end-1c'))}c")
                return "break"
            return h

        def select_all(_e=None):
            t.tag_add("sel", "1.0", "end-1c")
            t.mark_set("insert", "end-1c")
            return "break"

        def history(redo):
            def h(_e=None):
                try:
                    (t.edit_redo if redo else t.edit_undo)()
                except tk.TclError:
                    pass
                return "break"
            return h

        def generate(_e=None):
            self.generate()
            return "break"          # the Text's own Return binding must not add a line break

        for seq, fn in (("<Control-Left>", jump(-1, False)), ("<Control-Right>", jump(1, False)),
                        ("<Control-Shift-Left>", jump(-1, True)), ("<Control-Shift-Right>", jump(1, True)),
                        ("<Control-BackSpace>", kill(-1)), ("<Control-Delete>", kill(1)),
                        ("<Control-a>", select_all), ("<Control-A>", select_all),
                        ("<Control-z>", history(False)), ("<Control-Z>", history(True)), ("<Control-y>", history(True)),
                        ("<Control-Return>", generate), ("<Control-KP_Enter>", generate)):
            t.bind(seq, fn)

    def _spin(self, parent, var, frm, to, inc=1.0, width=6):
        return ttk.Spinbox(parent, textvariable=var, from_=frm, to=to, increment=inc, width=width)

    def _build(self, d):
        r = self.root
        pad = {"padx": 10, "pady": 4}

        self.f_tabs = ttk.Frame(r)      # one tab per model, two rows
        self.f_tabs.pack(fill="x", padx=10, pady=(8, 2))
        cols = 2                        # never more than two side by side (the window stays narrow, however many models)
        for c in range(cols):
            self.f_tabs.columnconfigure(c, weight=1, uniform="tab")
        self.rb_tabs = {}
        for i, m in enumerate(models.MODELS):
            rb = ttk.Radiobutton(self.f_tabs, text=m.label, value=m.key, variable=self.v_model, style="Tab.Toolbutton",
                                 command=self._on_model)
            rb.grid(row=i // cols, column=i % cols, sticky="ew", padx=2, pady=2)
            Tooltip(rb, m.tip)
            self.rb_tabs[m.key] = rb

        mf = ttk.Frame(r)
        mf.columnconfigure(1, weight=1)
        # Workflow and Text model live under "Advanced" (built below): the presets choose them.
        self.f_adv = ttk.Frame(r)
        self.adv_body = ttk.Frame(self.f_adv)
        self.adv_body.columnconfigure(1, weight=1)
        # Workflow and Preset are not shown: the model tabs choose the workflow and its settings (the widgets stay, the code
        # behind them is the same)
        self.cb_workflow = ttk.Combobox(self.adv_body, textvariable=self.v_workflow, state="readonly", width=8)
        self.cb_workflow.bind("<<ComboboxSelected>>", lambda e: self._workflow_picked())
        # the text model is chosen by the workflow / the LLM list under the prompt: no picker (the widget stays, never gridded)
        self.cb_clip = ttk.Combobox(self.adv_body, textvariable=self.v_clip, state="readonly", width=8)
        pf = ttk.Frame(self.adv_body)    # never gridded: presets are hidden
        pf.columnconfigure(1, weight=1)
        ttk.Label(pf, text="Preset").grid(row=0, column=0, sticky="w")
        self.cb_preset = ttk.Combobox(pf, textvariable=self.v_preset, state="readonly", width=8)
        self.cb_preset.bind("<<ComboboxSelected>>", lambda e: self.load_preset(self.v_preset.get()))
        self.cb_preset.grid(row=0, column=1, sticky="ew", padx=6)
        # icon buttons (drawn here: emoji do not render in Tk on Windows) leave the name list the room it needs
        self._icons = {"save": icon_image(self.root, "save", FG), "saveas": icon_image(self.root, "saveas", FG),
                       "delete": icon_image(self.root, "trash", ERROR_TEXT)}
        for col, (key, cmd, tip) in enumerate((("save", self.save_preset, "Save the preset under its name"),
                                               ("saveas", self.save_preset_as, "Save as a new preset…"),
                                               ("delete", self.delete_preset, "Delete the preset"))):
            b = ttk.Button(pf, image=self._icons[key], style="Icon.TButton", command=cmd)
            b.grid(row=0, column=2 + col, padx=(6 if col == 0 else 3, 0))
            Tooltip(b, tip)

        # "Compare base res / context" (a test series) are not shown; the code behind them stays (the fields are never gridded)
        e1 = ttk.Entry(self.adv_body, textvariable=self.v_cmp_res)
        e2 = ttk.Entry(self.adv_body, textvariable=self.v_cmp_ctx)
        self.f_enh = ttk.Frame(r)       # packed under Seed / Variants, above the prompt writer drop-down (see below)
        self.cb_enhance = ttk.Checkbutton(self.f_enh, text="LLM prompt enhancement", variable=self.v_enhance, command=self._on_workflow)
        self.cb_enhance.pack(side="left")
        self.tt_enhance = Tooltip(self.cb_enhance, ENHANCE_TIP)
        self._icons["copy"] = icon_image(self.root, "copy", FG)
        self._last_vgl = ""             # the prompt the text model wrote in the last run
        self.b_copy = ttk.Button(self.f_enh, image=self._icons["copy"], style="Icon.TButton", command=self._copy_enhanced, state="disabled")
        self.b_copy.pack(side="left", padx=(8, 0))
        self.tt_copy = Tooltip(self.b_copy, "Copy the prompt the text model wrote in the last run.")
        self.cb_turbo = ttk.Checkbutton(mf, text="LoRA", variable=self.v_turbo)
        self.cb_turbo.grid(row=1, column=1, sticky="w", padx=6, pady=(4, 0))
        self.tt_turbo = Tooltip(self.cb_turbo, LORA_TIP)

        self.f_lora = ttk.Frame(mf)    # strength of that LoRA
        self.f_lora.grid(row=2, column=1, sticky="ew", padx=6, pady=(2, 0))
        self.f_lora.columnconfigure(0, weight=1)
        self.w_lora_str = ttk.Scale(self.f_lora, from_=0.0, to=1.0, variable=self.v_lora_str, command=self._on_lora_str)
        self.w_lora_str.grid(row=0, column=0, sticky="ew")
        self.lbl_lora_str = ttk.Label(self.f_lora, width=5, style="Muted.TLabel")
        self.lbl_lora_str.grid(row=0, column=1, sticky="e", padx=(6, 0))
        Tooltip(self.w_lora_str, "LoRA strength (0 = off, 1 = full).")
        # up to three switchable stages of a workflow (SeedVR2, an optional LoRA, skip-layer guidance ...), each its own checkbox
        self.stage_vars = [self.v_stage, self.v_stage2, self.v_stage3]
        self.stage_cbs, self.stage_tips = [], []
        self.stage_scales, self.stage_lbls = [], []     # a stage that is a LoRA (MOSS' Lenovo) also has a strength slider
        for i, var in enumerate(self.stage_vars):
            cb = ttk.Checkbutton(mf, text="Stage", variable=var, command=self._update_stage_scales)
            cb.grid(row=3 + i, column=1, sticky="w", padx=6, pady=(2, 0))
            self.stage_tips.append(Tooltip(cb, STAGE_TIP))
            self.stage_cbs.append(cb)
            sf = ttk.Frame(mf)
            sf.grid(row=3 + i, column=2, sticky="e", padx=(0, 6), pady=(2, 0))
            sc = ttk.Scale(sf, from_=0.0, to=1.0, variable=self.v_sstr[i], length=self._px(110),
                           command=lambda _v=None: self._update_stage_scales())
            sc.pack(side="left")
            lb = ttk.Label(sf, width=5, style="Muted.TLabel")
            lb.pack(side="left", padx=(4, 0))
            Tooltip(sc, "LoRA strength (0 = off, 1 = full).")
            sf.grid_remove()
            self.stage_scales.append((sf, sc, lb))
        self.cb_stage = self.stage_cbs[0]
        for cb in self.stage_cbs:
            cb.grid_remove()
        self._on_lora_str()

        modes = ttk.Frame(r)
        modes.pack(fill="x", **pad)
        self.f_modes = modes
        self.f_opts = mf                # LoRA and stage switches of the workflow: shown only when it has some (_update_options_box)
        self.rb_modes = {}
        self.tt_modes = {}              # the tooltip of each mode button: the text of the selected model (see _update_mode_radios)
        for i, (key, label) in enumerate(MODE_LABELS):
            rb = ttk.Radiobutton(modes, text=label, value=key, variable=self.v_mode, command=self._on_mode)
            rb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=1)
            self.rb_modes[key] = rb
            self.tt_modes[key] = Tooltip(rb, MODE_TIPS[key])

        ff = ttk.Frame(r)               # shown only while a soft layer mask is used (see _update_feather_state)
        self.f_feather = ff
        ff.columnconfigure(1, weight=1)
        lbl_f = ttk.Label(ff, text="Edge feather", style="Muted.TLabel", width=14)
        lbl_f.grid(row=0, column=0, sticky="w")
        self.w_feather = sc = ttk.Scale(ff, from_=0, to=10, variable=self.v_feather, command=self._on_feather)
        sc.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_feather = ttk.Label(ff, width=9, style="Muted.TLabel", anchor="e")
        self.lbl_feather.grid(row=0, column=2, sticky="e")
        self._on_feather()
        for w in (lbl_f, sc):
            Tooltip(w, "Softens the seam between the new area and your picture, in % of the selection's shorter side. 0 = hard edge.")

        self.sep_prompt = ttk.Frame(r, style="Sep.TFrame", height=1)     # a light line above "Prompt"
        self.sep_prompt.pack(fill="x", padx=10, pady=(6, 4))
        self.f_ptop = ttk.Frame(r)      # "Prompt" and, where a mode has ready-made prompts, radio buttons that fill the field
        self.f_ptop.pack(fill="x", padx=10)
        ttk.Label(self.f_ptop, text="Prompt").pack(side="left")
        self.f_pchoice = ttk.Frame(self.f_ptop)
        self.f_pchoice.pack(side="left", padx=(10, 0))
        self.v_pchoice = tk.StringVar(value="")
        self._pchoice_key = None
        self.f_prompt = ttk.Frame(r)
        self.f_prompt.pack(fill="x", padx=10)
        try:
            lines = max(3, min(30, int(self.state.get("prompt_h", PROMPT_LINES))))
        except (TypeError, ValueError):
            lines = PROMPT_LINES
        self.t_prompt = self._text(self.f_prompt, lines)
        sb = ttk.Scrollbar(self.f_prompt, orient="vertical", command=self.t_prompt.yview)
        self.t_prompt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.t_prompt.pack(side="left", fill="x", expand=True)
        self.grip = ttk.Frame(r, style="Grip.TFrame", height=self._px(7), cursor="sb_v_double_arrow")
        self.grip.pack(fill="x", padx=10, pady=(1, 0))
        self._grip_drag(self.grip, self.t_prompt)
        Tooltip(self.grip, "Drag to resize the prompt field.")
        self.lbl_hint = ttk.Label(r, text=EXPAND_HINT, style="Hint.TLabel")   # Expand image, Upscale, Refine (see _update_prompt_hint)
        self.t_prompt.insert("1.0", self.state.get("prompt", ""))
        self.f_sharp = ttk.Frame(r)     # a light sharpening of the finished result, always at hand
        self.f_sharp.pack(fill="x", padx=10, pady=(6, 0))
        self.f_sharp.columnconfigure(1, weight=1)
        lb_sharp = ttk.Label(self.f_sharp, text="Sharpen result", style="Muted.TLabel", width=14)
        lb_sharp.grid(row=0, column=0, sticky="w")
        self.w_sharpen = ttk.Scale(self.f_sharp, from_=0.0, to=1.0, variable=self.v_sharpen, command=self._on_sharpen)
        self.w_sharpen.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_sharpen = ttk.Label(self.f_sharp, width=9, style="Muted.TLabel", anchor="e")
        self.lbl_sharpen.grid(row=0, column=2)
        Tooltip(self.w_sharpen, "Sharpens the finished result a little. 0 = off.")
        self._on_sharpen()
        self._sharp_widgets = (lb_sharp, self.w_sharpen, self.lbl_sharpen)   # hidden in Expand image
        lb_match = ttk.Label(self.f_sharp, text="Match colours", style="Muted.TLabel", width=14)
        lb_match.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.w_match = ttk.Scale(self.f_sharp, from_=0.0, to=1.0, variable=self.v_match, command=self._on_match)
        self.w_match.grid(row=1, column=1, sticky="ew", padx=8, pady=(2, 0))
        self.lbl_match = ttk.Label(self.f_sharp, width=9, style="Muted.TLabel", anchor="e")
        self.lbl_match.grid(row=1, column=2, pady=(2, 0))
        self._match_widgets = (lb_match, self.w_match, self.lbl_match)   # shown only where the function can use them
        Tooltip(self.w_match, "Pulls the new area's saturation back towards its surroundings. 0 = off.")
        self._on_match()
        self.f_neg = ttk.Frame(r)
        self.f_neg.pack(fill="x", padx=10, pady=(6, 0), before=self.f_sharp)     # directly under the prompt
        self.f_enh.pack(fill="x", padx=10, pady=(6, 0), before=self.f_sharp)
        self.v_neg_open = tk.BooleanVar(value=bool(self.state.get("neg_open", False)))
        self.btn_neg = ttk.Button(self.f_neg, command=self._toggle_negative, style="Link.TButton")
        self.btn_neg.pack(anchor="w")
        self.neg_body = ttk.Frame(self.f_neg)
        self.t_neg = self._text(self.neg_body, 2)
        self.t_neg.pack(fill="x")
        self.t_neg.insert("1.0", self.state.get("negative", d["negative"]))

        self.f_xl = ttk.Frame(self.adv_body)       # extra LoRAs: a search box with a drop-down and a strength each (under Advanced)
        self.f_xl.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.all_loras: list[str] = []
        self.lora_rows: list[dict] = []
        head = ttk.Frame(self.f_xl)
        head.pack(fill="x")
        ttk.Label(head, text="Extra LoRAs (style, detail ...)", style="Muted.TLabel").pack(side="left")
        self.b_addlora = ttk.Button(head, text="+ Add", style="Link.TButton", command=self._add_lora_row)
        self.b_addlora.pack(side="left", padx=8)
        Tooltip(self.b_addlora, "Adds an extra LoRA (strength 0 to 1.5).")
        self.f_xl_rows = ttk.Frame(self.f_xl)
        self.f_xl_rows.pack(fill="x")
        sf = ttk.Frame(r)    # Seed and Variants: directly under the negative prompt
        sf.pack(fill="x", padx=10, pady=(6, 0), after=self.f_neg)
        self.f_sf = sf
        mf.pack(fill="x", padx=10, pady=4, after=self.f_neg)     # the LoRA / stage box: directly under the negative prompt
        af = ttk.Frame(self.adv_body)
        af.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        items = [("Seed (-1 random)", self._spin(sf, self.v_seed, -1, 2**31 - 1, 1, 11)),
                 ("Variants", self._spin(sf, self.v_variants, 1, 8, 1, 4)),
                 ("Steps", self._spin(af, self.v_steps, 1, 150, 1, 5)),
                 ("CFG", self._spin(af, self.v_cfg, 1, 30, 0.5, 5)),
                 ("Denoise", self._spin(af, self.v_denoise, 0.05, 1.0, 0.05, 5))]
        for i, (lbl, w) in enumerate(items):
            parent = sf if i < 2 else af
            col = i if i < 2 else i - 2
            ttk.Label(parent, text=lbl, style="Muted.TLabel").grid(row=0, column=col, sticky="w", padx=(0, 6))
            w.grid(row=1, column=col, sticky="w", padx=(0, 6))
        self.w_denoise = items[4][1]
        self.w_variants = items[1][1]
        self.w_steps, self.w_cfg = items[2][1], items[3][1]
        self.recipe_widgets = [items[2][1], items[3][1]]

        sm = ttk.Frame(self.adv_body)
        sm.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        sm.columnconfigure((1, 3), weight=1)
        ttk.Label(sm, text="Sampler", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.cb_sampler = ttk.Combobox(sm, textvariable=self.v_sampler, width=10)
        self.cb_sampler.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(sm, text="Scheduler", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.cb_sched = ttk.Combobox(sm, textvariable=self.v_scheduler, width=9)
        self.cb_sched.grid(row=0, column=3, sticky="ew", padx=6)
        self.recipe_widgets += [self.cb_sampler, self.cb_sched]

        self.v_adv_open = tk.BooleanVar(value=bool(self.state.get("adv_open", False)))
        self.btn_adv = ttk.Button(self.f_adv, command=self._toggle_advanced, style="Link.TButton")
        self.sep_adv = ttk.Frame(self.f_adv, style="Sep.TFrame", height=1)     # a light line above "Advanced"
        self.sep_adv.pack(fill="x", pady=(0, 6))
        self.btn_adv.pack(anchor="w")
        self.f_adv.pack(fill="x", padx=10, pady=4)
        self._show_advanced()
        self._show_negative()

        self.f_scale = ttk.Frame(r)
        ttk.Label(self.f_scale, text="Upscale: opens new document", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.cb_scale = ttk.Combobox(self.f_scale, textvariable=self.v_scale, values=["x 1.5", "x 2", "x 3", "x 4"], state="readonly", width=6)
        self.cb_scale.grid(row=0, column=1, padx=8)
        self.f_scale.columnconfigure(0, weight=1)
        self.f_detail = ttk.Frame(r)      # Upscale and Refine
        self.f_detail.columnconfigure(1, weight=1)
        ttk.Label(self.f_detail, text="Mix source image/new image", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.w_detail = ttk.Scale(self.f_detail, from_=0.0, to=1.0, variable=self.v_detail, command=self._on_detail)
        self.w_detail.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_detail = ttk.Label(self.f_detail, width=5, style="Muted.TLabel")
        self.lbl_detail.grid(row=0, column=2)
        Tooltip(self.w_detail, "100 % = only the new image; less mixes in the plain scaled original (tames over-sharp results).")
        self._on_detail()

        self.f_desc = ttk.Frame(r)        # Upscale and Refine: a text model describes the picture, the description joins the prompt
        self.f_desc.columnconfigure(1, weight=1)
        self.cb_describe = ttk.Checkbutton(self.f_desc, text="Send LLM description", variable=self.v_describe)
        self.cb_describe.grid(row=0, column=0, sticky="w")
        self.cb_dpos = ttk.Combobox(self.f_desc, textvariable=self.v_desc_pos, values=list(DESC_POS.values()), state="readonly", width=18)
        self.cb_dpos.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.b_copy2 = ttk.Button(self.f_desc, image=self._icons["copy"], style="Icon.TButton", command=self._copy_enhanced, state="disabled")
        self.b_copy2.grid(row=0, column=2, padx=(6, 0))
        Tooltip(self.b_copy2, "Copy the description the text model wrote in the last run.")
        lb_dmp = ttk.Label(self.f_desc, text="Resize for analysis", style="Muted.TLabel")
        lb_dmp.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.cb_dmp = ttk.Combobox(self.f_desc, textvariable=self.v_desc_mp, values=[desc_mp_text(x) for x in (0.25, 0.5, 1, 2, 0)],
                                   state="readonly", width=18)
        self.cb_dmp.grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(2, 0))
        Tooltip(self.cb_describe, "A text model looks at the picture and adds its description to the prompt.")
        Tooltip(self.cb_dpos, "Where the description goes.")
        Tooltip(self.cb_dmp, "The picture is scaled down for the text model: smaller = faster.")

        self.f_ref = ttk.LabelFrame(r, text="Reference image")
        ttk.Label(self.f_ref, text="The top layer is the reference. Select where it should go.\nEverything below it is the picture.",
                  style="Muted.TLabel", justify="left", wraplength=self._px(360)).pack(anchor="w", padx=6, pady=(0, 2))
        sty = ttk.Frame(self.f_ref)
        sty.pack(fill="x", padx=6, pady=(0, 4))
        lbs = ttk.Label(sty, text="Style", style="Muted.TLabel")
        lbs.pack(side="left")
        self.cb_refstyle = ttk.Combobox(sty, textvariable=self.v_refstyle, values=list(REF_STYLES.values()), state="readonly", width=22)
        self.cb_refstyle.pack(side="left", padx=6)
        self.cb_refstyle.bind("<<ComboboxSelected>>", lambda e: self._update_availability())
        for w in (lbs, self.cb_refstyle):
            Tooltip(w, "Classic: long instruction, reference first. Simple: one short sentence, picture first.")
        self.cb_cutout = ttk.Checkbutton(self.f_ref, text="Cut out the reference (remove its background)", variable=self.v_cutout)
        self.cb_cutout.pack(anchor="w", padx=6, pady=(0, 4))
        Tooltip(self.cb_cutout, "Asks the model to remove the reference's background first.")
        self.cb_collage = ttk.Checkbutton(self.f_ref, text="Rough placement in the picture", variable=self.v_collage)
        self.cb_collage.pack(anchor="w", padx=6, pady=(0, 6))
        Tooltip(self.cb_collage, "Pastes a rough copy of the reference into the selection to show where it goes.")

        self.f_img = ttk.LabelFrame(self.adv_body, text="Image and mask")
        self.f_img.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        tips = {
            "Base res.": "Size (px) the model works at. Higher = more detail, slower.",
            "Context": "Surroundings the model sees, as a fraction of the selection's longer side.",
            "Mask grow": "Grows the model's mask by this many px (mask workflows only).",
            "Mask blur": "Softens the model's mask edge (mask workflows only).",
        }
        self.w_adv = {}
        for i, (lbl, var, lo, hi, inc) in enumerate((("Base res.", self.v_res, 256, 2048, 64),
                                                    ("Context", self.v_context, 0, 2, 0.1),
                                                    ("Mask grow", self.v_grow, 0, 128, 2),
                                                    ("Mask blur", self.v_blur, 0, 128, 2))):
            lb = ttk.Label(self.f_img, text=lbl, style="Muted.TLabel")
            lb.grid(row=0, column=i, sticky="w", padx=6)
            sp = self._spin(self.f_img, var, lo, hi, inc, 6)
            sp.grid(row=1, column=i, padx=6, pady=(0, 6))
            self.w_adv[lbl] = sp
            Tooltip(lb, tips[lbl])
            Tooltip(sp, tips[lbl])
        self.cb_fooocus = ttk.Checkbutton(self.f_img, text="Fooocus inpaint (SDXL, as in Krita AI Diffusion)", variable=self.v_fooocus)
        self.cb_fooocus.grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))
        Tooltip(self.cb_fooocus, "Built-in SDXL inpaint graph only.")
        lm = ttk.Frame(r)               # under the edge feather, outside Advanced
        self.f_lm = lm
        lm.pack(fill="x", padx=10, pady=(2, 4), before=self.f_adv)
        lb = ttk.Label(lm, text="Layer mask", style="Muted.TLabel")
        lb.pack(side="left")
        self.cb_lm = cb_lm = ttk.Combobox(lm, textvariable=self.v_lmask, values=list(LAYER_MASKS.values()), state="readonly", width=18)
        cb_lm.pack(side="left", padx=6)
        cb_lm.bind("<<ComboboxSelected>>", lambda e: self._update_feather_state())
        for w in (lb, cb_lm):
            Tooltip(w, "How the result is blended into your picture: auto (recommended), soft (feathered), hard (selection as is), none.")

        bf = ttk.Frame(r)
        bf.pack(fill="x", padx=10, pady=(8, 2))
        self.b_go = ttk.Button(bf, text="Generate", width=11, style="Accent.TButton", command=self.generate)
        self.b_go.pack(side="left", fill="y")
        Tooltip(self.b_go, "Generate (Ctrl+Enter)")
        self.b_stop = ttk.Button(bf, text="Cancel", command=self.stop, state="disabled")
        self.b_stop.pack(side="left", fill="y", padx=(6, 0))
        self._icons.update({"undo": icon_image(self.root, "undo", FG), "redo": icon_image(self.root, "redo", FG)})
        self.b_undo = ttk.Button(bf, image=self._icons["undo"], style="Icon.TButton", command=self.undo_edit)
        self.b_undo.pack(side="left", fill="y", padx=(6, 0))
        self.b_redo = ttk.Button(bf, image=self._icons["redo"], style="Icon.TButton", command=self.redo_edit)
        self.b_redo.pack(side="left", fill="y", padx=(6, 0))
        Tooltip(self.b_redo, "Brings the AI edit back after an Undo.")
        Tooltip(self.b_undo, "Back to the state before the last generation.")

        # one bar for the whole run (prompt, then image) with the current step written next to it
        self.v_pl = tk.StringVar(value="")
        row = ttk.Frame(r)
        row.pack(fill="x", padx=10, pady=(6, 0))
        self.lbl_pl = ttk.Label(row, textvariable=self.v_pl, style="Muted.TLabel")    # above the bar, the full width: never covered by it
        self.lbl_pl.pack(anchor="w")
        self.pb = ttk.Progressbar(row, mode="determinate", maximum=1.0)
        self.pb.pack(fill="x", pady=(2, 0))
        self._bar_value = 0.0
        st = ttk.Frame(r)
        st.pack(fill="x", padx=10, pady=(4, 0))
        self.lbl_err = ttk.Label(st, text="!", style="Badge.TLabel", width=2, anchor="center")
        self.lbl_status = ttk.Label(st, textvariable=self.v_status, wraplength=self._px(MIN_W - 40), justify="left")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        foot = ttk.Frame(r)
        foot.pack(fill="x", side="bottom", padx=10, pady=6)
        ttk.Label(foot, textvariable=self.v_conn, style="Muted.TLabel").pack(side="left")
        b_refresh = ttk.Button(foot, text="Refresh", command=self.refresh)
        b_refresh.pack(side="left", padx=(8, 0))
        Tooltip(b_refresh, "Reads PhotoCraft's and ComfyUI's state again: connection, installed LoRAs, samplers, text models, workflows.")
        b_reset = ttk.Button(foot, text="Reset", command=self.reset_settings)
        b_reset.pack(side="left", padx=(6, 0))
        Tooltip(b_reset, "Back to the startup settings of this tab and function.")

        for cb in (self.cb_scale, self.cb_lm, self.cb_refstyle, self.cb_sampler, self.cb_sched, self.cb_dpos, self.cb_dmp):
            self._open_on_click(cb)         # the list opens on a click anywhere in the box, not only on the arrow
        self._fit_job = None
        r.bind("<Configure>", self._on_content_size, add="+")      # the window follows its content: nothing hangs off the bottom
        self.root.bind("<Button-1>", self._lora_outside, add="+")
        self.root.bind("<Control-Return>", lambda e: (self.generate(), "break")[1])
        self.root.bind("<Escape>", lambda e: self.stop())

    def _switch_context(self, mode: str):
        """Keep each mode's own Context value: store the old one, show the new one's."""
        try:
            self._ctx[self._ctx_mode] = float(self.v_context.get())
        except tk.TclError:
            pass
        if mode != self._ctx_mode:
            self.v_context.set(self._ctx.get(mode, self._ctx_default))
            self._ctx_mode = mode

    def _on_mode_ui(self):
        mode = self.v_mode.get()
        self._switch_context(mode)
        if self._run_mode() in SCALE_MODES:
            self.f_desc.pack(fill="x", padx=10, pady=4, after=self.f_sharp)
        else:
            self.f_desc.pack_forget()
        if mode == "upscale":
            self.f_scale.pack(fill="x", padx=10, pady=4, after=self.f_sharp)
        else:
            self.f_scale.pack_forget()
        if self._run_mode() in SCALE_MODES:
            self.f_detail.pack(fill="x", padx=10, pady=4, after=self.f_sharp)
        else:
            self.f_detail.pack_forget()
        if mode == "reference":
            self.f_ref.pack(fill="x", padx=10, pady=4, after=self.f_sharp)
        else:
            self.f_ref.pack_forget()
        self.w_denoise.configure(state="disabled" if mode == "txt2img" or self._ignores_mask() else "normal")   # an editor always runs at 1.0
        expand = mode == "outpaint"        # Expand image: the plugin's own defaults, none of the finishing options
        if self._run_mode() in ("txt2img", "edit") + SCALE_MODES or expand:    # nothing to blend into / a new document / the whole picture: no layer mask
            self.f_lm.pack_forget()
        elif not self.f_lm.winfo_manager():
            self.f_lm.pack(fill="x", padx=10, pady=(2, 4), before=self.f_adv)
        for w in self._match_widgets:      # pulling colours back only makes sense where a new area meets the old picture
            if mode in ("inpaint", "reference"):
                w.grid()
            else:
                w.grid_remove()
        for w in self._sharp_widgets:
            if expand:
                w.grid_remove()
            else:
                w.grid()
        self.f_sharp.pack_configure(pady=0 if expand else (6, 0))
        self._show_enhance_box(not expand)
        self._update_prompt_hint()
        self._sync_prompt_field(mode)
        self._update_feather_state()
        self._update_availability()
        if self._sized:
            self._fit_height()

    def _show_enhance_box(self, on: bool):
        """The "LLM prompt enhancement" row (with the copy button): not in Expand image."""
        shown = bool(self.f_enh.winfo_manager())
        if on and not shown:
            self.f_enh.pack(fill="x", padx=10, pady=(6, 0), before=self.f_sharp)
        elif not on and shown:
            self.f_enh.pack_forget()
        if on != shown and getattr(self, "_sized", False):
            self._fit_height()

    def _run_mode(self) -> str:
        """The mode the bridge runs: the selected one, unless the model's mode says otherwise (Fibo Refine runs as Edit)."""
        mode = self.v_mode.get()
        m = self._model()
        spec = m.modes.get(mode) if m else None
        return (spec.run_as if spec and spec.run_as else mode)

    def _ref_style(self) -> str:
        return {v: k for k, v in REF_STYLES.items()}.get(self.v_refstyle.get(), "simple")

    def _desc_mp(self) -> float:
        t = str(self.v_desc_mp.get()).strip().lower()
        try:
            return 0.0 if t.startswith("full") else max(0.05, float(t.replace("mp", "").strip()))
        except ValueError:
            return 0.5

    def _desc_pos(self) -> str:
        return {v: k for k, v in DESC_POS.items()}.get(self.v_desc_pos.get(), "front")

    def _scale(self) -> float:
        try:
            return min(8.0, max(1.0, float(str(self.v_scale.get()).strip().lstrip("xX×").strip().replace(",", "."))))
        except ValueError:
            return 2.0

    def _prompt_text(self) -> str:
        """The prompt to save: in Remove object the field is empty, the user's own text is kept aside."""
        if str(self.t_prompt.cget("state")) == "disabled":
            return getattr(self, "_prompt_kept", "")
        return self.t_prompt.get("1.0", "end").strip()

    def _grip_drag(self, grip, t):
        """The strip under the prompt field: drag it to change the field's height (in lines)."""
        st: dict = {}

        def line_h():
            try:
                return max(8, int(t.tk.call("font", "metrics", t.cget("font"), "-linespace")))
            except Exception:
                return self._px(16)

        def press(e):
            st.update(y=e.y_root, h=self._prompt_lines(), lh=line_h())

        def move(e):
            if "y" not in st:
                return
            n = max(3, min(30, st["h"] + round((e.y_root - st["y"]) / st["lh"])))
            if n != self._prompt_lines():
                t.configure(height=n)
                self._fit_height()
        grip.bind("<ButtonPress-1>", press)
        grip.bind("<B1-Motion>", move)

    def _prompt_lines(self) -> int:
        try:
            return int(self.t_prompt.cget("height"))
        except (TypeError, ValueError, tk.TclError):
            return PROMPT_LINES

    def _update_prompt_hint(self):
        """The prompt field turns orange with a hint under it: Expand (an empty prompt often fills best), and the modes whose
        prompt starts with the workflow's own text (Upscale / Refine: describe the image in front of it)."""
        mode = self.v_mode.get()
        m = self._model()
        spec = m.modes.get(mode) if m else None
        text = EXPAND_HINT if mode == "outpaint" else (spec.prompt_tip if spec else "")
        on = bool(text)
        self._hint_text = text
        self.t_prompt.configure(highlightbackground=ACCENT if on else "#454545", highlightthickness=2 if on else 1)
        if on:
            self.lbl_hint.configure(text=text)
            self.lbl_hint.pack(anchor="w", padx=10, after=self.grip)
        else:
            self.lbl_hint.pack_forget()

    def _copy_enhanced(self):
        """The prompt the text model wrote in the last run goes to the clipboard."""
        text = (self._last_vgl or "").strip()
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            self._status("Copied to the clipboard.")
        except tk.TclError as e:
            self._status(f"Could not copy: {e}", error=True)

    def _update_prompt_choices(self):
        """Ready-made prompts of a mode (Flux 2 refine): radio buttons next to "Prompt" that put the text into the field."""
        m = self._model()
        spec = m.modes.get(self.v_mode.get()) if m else None
        choices = spec.prompts if spec else ()
        key = (m.key, self.v_mode.get()) if choices else None
        if key == self._pchoice_key:
            return
        self._pchoice_key = key
        for w in (self.f_pchoice.winfo_children() or []):
            w.destroy()
        if not choices:
            return
        cur = self.t_prompt.get("1.0", "end").strip()
        self.v_pchoice.set(next((lb for lb, text, _ in choices if text.strip() == cur), ""))
        for label, text, tip in choices:
            rb = ttk.Radiobutton(self.f_pchoice, text=label, value=label, variable=self.v_pchoice,
                                 command=lambda t=text: self._insert_prompt(t))
            rb.pack(side="left", padx=(0, 8))
            Tooltip(rb, tip)

    def _insert_prompt(self, text: str):
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        t.delete("1.0", "end")
        t.insert("1.0", text)

    def _sync_prompt_field(self, mode: str):
        """Remove object ignores the text: the field is emptied and greyed out, the typed text comes back afterwards."""
        t = self.t_prompt
        m = self._model()
        spec = m.modes.get(mode) if m else None
        if mode == "remove" and not (spec is not None and spec.remove_text):
            if str(t.cget("state")) != "disabled":
                self._prompt_kept = t.get("1.0", "end").strip()
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.configure(state="disabled")
        elif str(t.cget("state")) == "disabled":
            t.configure(state="normal")
            t.delete("1.0", "end")
            if getattr(self, "_prompt_kept", ""):
                t.insert("1.0", self._prompt_kept)
            self._prompt_kept = ""

    def _px(self, n: int) -> int:
        return round(n * getattr(self, "ui", 1.0))

    # ---------- extra LoRAs ----------

    LORA_MAX = 4
    LORA_HINTS = {"qwen": ("qwen",), "flux2": ("flux 2", "flux2", "flux_2"), "flux3": ("flux 3", "flux3", "flux_3"),
                  "moss": ("moss",), "fibo": ("fibo", "bria")}

    def _lora_choices(self, typed: str = "") -> list[str]:
        """The LoRA list for a drop-down: this model's folder first, filtered by what was typed (all words, any case)."""
        hints = self.LORA_HINTS.get(self.v_model.get(), ())
        names = sorted(self.all_loras, key=lambda n: (not any(h in n.lower() for h in hints), n.lower()))
        words = typed.lower().split()
        return [n for n in names if all(w in n.lower() for w in words)]

    def _add_lora_row(self, name: str = "", strength: float = 1.0):
        if len(self.lora_rows) >= self.LORA_MAX:
            return
        row = ttk.Frame(self.f_xl_rows)
        row.pack(fill="x", pady=1)
        row.columnconfigure(0, weight=1)
        v_name, v_str = tk.StringVar(value=name), tk.DoubleVar(value=strength)
        rec = {"frame": row, "name": v_name, "strength": v_str, "list": None, "box": None}
        ent = ttk.Entry(row, textvariable=v_name)
        ent.grid(row=0, column=0, sticky="ew")
        rec["entry"] = ent
        btn = ttk.Button(row, text="\u25be", style="Link.TButton", width=2, command=lambda: self._lora_toggle(rec))
        btn.grid(row=0, column=1, padx=(2, 0))
        rec["btn"] = btn
        sp = ttk.Spinbox(row, textvariable=v_str, from_=0.0, to=1.5, increment=0.05, width=5)
        sp.grid(row=0, column=2, padx=4)
        rm = ttk.Button(row, text="x", style="Link.TButton", width=2, command=lambda: self._remove_lora_row(rec))
        rm.grid(row=0, column=3)
        # typing opens a list under the row that narrows with every key; a click (or Down, Enter) takes the entry
        ent.bind("<KeyRelease>", lambda e: self._lora_key(rec, e))
        ent.bind("<Down>", lambda e: self._lora_focus_list(rec))
        ent.bind("<Escape>", lambda e: (self._lora_hide(rec), "break")[1])
        Tooltip(rm, "Remove this LoRA")
        Tooltip(btn, "Show all LoRAs")
        Tooltip(ent, "Type to search, click a LoRA to take it.")
        self.lora_rows.append(rec)
        self.b_addlora.configure(state="normal" if len(self.lora_rows) < self.LORA_MAX else "disabled")

    def _lora_key(self, rec: dict, e):
        if getattr(e, "keysym", "") in ("Return", "Escape", "Tab", "Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self._lora_show(rec, rec["name"].get())

    def _lora_toggle(self, rec: dict):
        if rec.get("box") is not None:
            self._lora_hide(rec)
        else:
            self._lora_show(rec, "")

    def _lora_show(self, rec: dict, typed: str = ""):
        """The list under a LoRA row: the matches for what was typed (scrollable; a click takes one)."""
        try:
            names = self._lora_choices(typed)[:400]
            if not names:
                self._lora_hide(rec)
                return
            box = rec.get("box")
            if box is None:
                box = ttk.Frame(self.f_xl_rows)
                lb = tk.Listbox(box, height=8, exportselection=False, activestyle="none", bg=PANEL, fg=FG,
                                selectbackground=ACCENT, selectforeground="#1b1b1b", relief="flat", highlightthickness=1,
                                highlightbackground="#454545", font=(FONT, 9))
                sb = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
                lb.configure(yscrollcommand=sb.set)
                sb.pack(side="right", fill="y")
                lb.pack(side="left", fill="both", expand=True)
                box.pack(fill="x", after=rec["frame"])
                lb.bind("<ButtonRelease-1>", lambda e: self._lora_pick(rec))
                lb.bind("<Return>", lambda e: self._lora_pick(rec))
                lb.bind("<Escape>", lambda e: (self._lora_hide(rec), rec["entry"].focus_set(), "break")[2])
                rec["box"], rec["list"] = box, lb
            lb = rec["list"]
            lb.configure(height=max(1, min(8, len(names))))
            lb.delete(0, "end")
            for n in names:
                lb.insert("end", n)
            if self._sized:
                self._fit_height()
        except Exception as e:      # shown instead of silently doing nothing
            self._status(f"LoRA list: {e}", error=True)

    def _lora_focus_list(self, rec: dict):
        if rec.get("box") is None:
            self._lora_show(rec, rec["name"].get())
        lb = rec.get("list")
        if lb is not None:
            lb.focus_set()
            lb.selection_set(0)
            lb.activate(0)
        return "break"

    def _lora_pick(self, rec: dict):
        lb = rec.get("list")
        if lb is None:
            return
        sel = lb.curselection()
        if sel:
            rec["name"].set(lb.get(sel[0]))
        self._lora_hide(rec)
        rec["entry"].focus_set()

    def _lora_hide(self, rec: dict):
        box = rec.get("box")
        if box is not None:
            box.destroy()
            rec["box"] = rec["list"] = None
            if self._sized:
                self._fit_height()

    def _lora_outside(self, e):
        """A click anywhere but in a LoRA row or its list closes the lists."""
        for rec in list(self.lora_rows):
            if rec.get("box") is None:
                continue
            w = str(e.widget)
            if w.startswith(str(rec["box"])) or w in (str(rec["entry"]), str(rec["btn"])):
                continue
            self._lora_hide(rec)

    def _remove_lora_row(self, rec: dict):
        if rec in self.lora_rows:
            self.lora_rows.remove(rec)
            self._lora_hide(rec)
            rec["frame"].destroy()
        self.b_addlora.configure(state="normal")
        self._fit_height()

    def _loras(self) -> list[list]:
        """What the rows say: [[file, strength], ...] for the rows with a name."""
        out = []
        for r in self.lora_rows:
            n = r["name"].get().strip()
            if n:
                try:
                    out.append([n, round(float(r["strength"].get()), 2)])
                except (tk.TclError, ValueError):
                    out.append([n, 1.0])
        return out

    def _set_loras(self, items):
        for r in list(self.lora_rows):
            self._remove_lora_row(r)
        for n, st in (items or [])[: self.LORA_MAX]:
            self._add_lora_row(str(n), float(st))

    def _model(self):
        return models.BY_KEY.get(self.v_model.get())

    def _update_mode_radios(self):
        """Only what the chosen model does well can be picked (the rest is greyed out in its place); a model-less workflow
        of your own keeps everything. The buttons follow each other without gaps, two per row."""
        m = self._model()
        shown = []
        for key, _label in MODE_LABELS:
            rb = self.rb_modes[key]
            if key == "img2img" and m is not None:
                rb.grid_remove()           # nothing in the tabs uses it
                continue
            rb.configure(state="normal" if (m is None or key in m.modes) else "disabled")
            self.tt_modes[key].text = (m.mode_tips.get(key) if m is not None else None) or MODE_TIPS[key]
            shown.append(key)
        for i, key in enumerate(shown):
            self.rb_modes[key].grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=1)
    def _on_model(self):
        """A tab was clicked: keep the mode when the model has it, else its first one; start with the model's settings."""
        m = self._model()
        if m is None:
            return
        self._reset_detail()
        if self.v_mode.get() not in m.modes:
            self.v_mode.set(next(iter(m.modes)))
        self._apply_model_mode(force=True)
        self._on_mode_ui()
        self._on_workflow()
        self._fit_height()

    def _apply_model_mode(self, force: bool = False):
        """The mode (or tab) changed: its workflow (unless you picked another one of this model under Advanced) and its
        starting settings. Settings you never touch stay what the model's mode defines."""
        m = self._model()
        if m is None or getattr(self, "_booting", False):
            return
        mode = self.v_mode.get()
        if mode not in m.modes:
            mode = next(iter(m.modes))
            self.v_mode.set(mode)
        spec = m.modes[mode]
        wf = self.v_workflow.get()
        keep = wf in m.workflows() and wf == spec.workflow
        s = {"match": 0.0, **spec.settings}      # the colour pull-back belongs to the model's mode, it does not travel to the next tab
        if not keep:
            s["workflow"] = spec.workflow
        else:
            s.pop("enhance", None)       # same workflow: the "LLM prompt enhancement" checkbox keeps what you set (Expand ignores it)
        self._switch_context(mode)   # first: the context memory belongs to the mode, the defaults below overwrite its value
        self._apply_settings(s)
        t = self.t_prompt
        cur = t.get("1.0", "end").strip() if str(t.cget("state")) != "disabled" else ""
        if (cur == "" or cur in models.STOCK_PROMPTS) and str(t.cget("state")) != "disabled":   # an unedited stock text is replaced
            t.delete("1.0", "end")
            if spec.prompt_hint:
                t.insert("1.0", spec.prompt_hint)
        self._update_mode_radios()
        self._update_prompt_choices()
        self._update_prompt_hint()

    def _sync_model(self):
        """The window was set from a preset / the saved state / the workflow list: show the tab that belongs to it."""
        wf = self.v_workflow.get()
        m = models.model_for_workflow(wf) if wf and wf != BUILTIN else None
        cur = self._model()
        if m is not None and (cur is None or wf not in cur.workflows()):
            self.v_model.set(m.key)
        elif m is None and wf and cur is not None and wf not in cur.workflows():
            self.v_model.set("")        # a workflow of your own: no tab, nothing restricted
        self._update_mode_radios()

    def _show_negative(self):
        opened = bool(self.v_neg_open.get())
        self.btn_neg.configure(text=("\u25be Negative prompt" if opened else "\u25b8 Negative prompt"))
        if opened:
            self.neg_body.pack(fill="x", pady=(4, 0))
        else:
            self.neg_body.pack_forget()

    def _toggle_negative(self):
        self.v_neg_open.set(not self.v_neg_open.get())
        self._show_negative()
        self._fit_height()

    def _show_advanced(self):
        opened = bool(self.v_adv_open.get())
        self.btn_adv.configure(text=("\u25be Advanced" if opened else "\u25b8 Advanced"))
        if opened:
            self.adv_body.pack(fill="x", pady=(4, 0))
        else:
            self.adv_body.pack_forget()

    def _toggle_advanced(self):
        self.v_adv_open.set(not self.v_adv_open.get())
        self._show_advanced()
        self._fit_height()

    def _on_content_size(self, _event=None):
        """The content changed its size (a section appeared, text wrapped): fit the window again, once, a moment later."""
        if not getattr(self, "_sized", False) or self._fit_job is not None:
            return

        def fit():
            self._fit_job = None
            try:
                if abs(self.root.winfo_reqheight() - self.root.winfo_height()) > 2:
                    self._fit_height()
            except tk.TclError:
                pass
        self._fit_job = self.root.after(60, fit)

    def _fit_height(self, width: int | None = None):
        """The window is MIN_W wide (fixed) and exactly as high as its content needs."""
        self.root.update_idletasks()
        w, h = self._px(MIN_W), max(self._px(320), self.root.winfo_reqheight())
        self.root.geometry(f"{w}x{h}")

    def _reset_detail(self):
        """"Mix source image/new image" starts at 100 % (only the new image) whenever a function or tab is chosen."""
        if not getattr(self, "_booting", False):
            self.v_detail.set(1.0)
            self._on_detail()

    def _on_mode(self):
        self._reset_detail()
        if self.v_model.get():
            self._apply_model_mode()
        else:
            self._couple_workflow()
        self._on_mode_ui()
        self._on_workflow()  # the text model is not used in reference mode
        mode = self.v_mode.get()
        if mode in ("inpaint", "remove", "reference", "outpaint", "edit"):
            self.v_denoise.set(1.0)  # full denoise inside the mask; lower it to keep more of the original
        elif mode == "img2img" and self.v_denoise.get() >= 0.99 and not self._ignores_mask():
            self.v_denoise.set(0.6)   # not for Fibo-type editors: below 1.0 they produce a different, broken picture

    def reset_settings(self):
        """Everything in the window back to what a fresh start has: this tab and function stay, their starting settings come back,
        the prompt, the negative prompt, extra LoRAs, seed and the finishing sliders are cleared."""
        if self.worker and self.worker.is_alive():
            return
        d = self.cfg["defaults"]
        self.v_seed.set(-1)
        self.v_variants.set(int(d["variants"]))
        self.v_grow.set(int(d["mask_grow"]))
        self.v_blur.set(int(d["mask_blur"]))
        self.v_overlap.set(int(d["overlap"]))
        self.v_res.set(int(d["base_res"]))
        self.v_denoise.set(float(d["denoise"]))
        self.v_sharpen.set(0.0)
        self.v_match.set(0.0)
        self.v_feather.set(2.0)
        self.v_detail.set(1.0)
        self.v_describe.set(False)
        self.v_desc_pos.set(DESC_POS["front"])
        self.v_desc_mp.set(desc_mp_text(0.5))
        self.v_lmask.set(LAYER_MASKS["auto"])
        self.v_refstyle.set(REF_STYLES["simple"])
        self.v_collage.set(True)
        self.v_cutout.set(True)
        self.v_cmp_res.set("")
        self.v_cmp_ctx.set("")
        self.v_scale.set(scale_text(1.5))
        self.t_neg.delete("1.0", "end")
        if str(self.t_prompt.cget("state")) != "disabled":
            self.t_prompt.delete("1.0", "end")
        self._prompt_kept = ""
        self._set_loras([])
        self._ctx = {"inpaint": FILL_CONTEXT}
        self.v_context.set(self._ctx.get(self.v_mode.get(), d["context"]))
        self._ctx_mode = self.v_mode.get()
        self._vals_key = None                    # steps / CFG / sampler / scheduler are read from the workflow again
        if self.v_model.get():
            self._apply_model_mode(force=True)
        self._on_mode_ui()
        self._on_workflow()
        self._on_sharpen()
        self._on_match()
        self._on_feather()
        self._fit_height()
        self._status("Reset to the startup settings.")

    def _status(self, msg: str, error: bool = False):
        """The status line. An error gets a red "!" badge and red text, it never opens a dialog."""
        self.v_status.set(msg)
        self.lbl_status.configure(style="Error.TLabel" if error else "TLabel")
        if error:
            self.lbl_err.pack(side="left", padx=(0, 8), before=self.lbl_status)
        else:
            self.lbl_err.pack_forget()

    def _uses_soft_mask(self) -> bool:
        """True when the new layer really gets the soft (feathered) layer mask, i.e. the feather has an effect."""
        choice = {v: k for k, v in LAYER_MASKS.items()}.get(self.v_lmask.get(), "auto")
        if self.v_mode.get() == "txt2img":
            return False
        if choice != "auto":
            return choice == "soft"
        if self.v_mode.get() == "upscale":
            return False
        if self.v_mode.get() not in ("inpaint", "remove", "reference", "outpaint"):
            return True
        return not self._ignores_mask()

    def _ignores_mask(self) -> bool:
        """True when the selected workflow never uses the mask (a Fibo-type instruction editor)."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return False
        try:
            return not any(mask_is_used(load_template(w)) for w in resolve(self.workflows_dir / wf))
        except (OSError, ValueError, KeyError):
            return False

    def _update_feather_state(self):
        """The edge feather is shown only while it has an effect (a soft layer mask is used)."""
        on = self._uses_soft_mask() and self.v_mode.get() not in ("outpaint", "upscale", "refine")
        self.w_feather.configure(state="normal" if on else "disabled")
        shown = bool(self.f_feather.winfo_manager()) if hasattr(self.f_feather, "winfo_manager") else False
        if on and not shown:
            self.f_feather.pack(fill="x", padx=10, pady=(4, 0), before=self.f_lm if self.f_lm.winfo_manager() else self.f_adv)
        elif not on and shown:
            self.f_feather.pack_forget()
        if on != shown and getattr(self, "_sized", False):
            self._fit_height()

    def _on_lora_str(self, _value=None):
        self.lbl_lora_str.configure(text=f"{float(self.v_lora_str.get()):.2f}")

    def _on_match(self, _value=None):
        self.lbl_match.configure(text=f"{round(float(self.v_match.get()) * 100)} %")

    def _on_sharpen(self, _value=None):
        self.lbl_sharpen.configure(text=f"{round(float(self.v_sharpen.get()) * 100)} %")

    def _on_detail(self, _value=None):
        self.lbl_detail.configure(text=f"{round(float(self.v_detail.get()) * 100)} %")

    def _wf_templates(self):
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return []
        try:
            return [load_template(w) for w in resolve(self.workflows_dir / wf)]
        except (OSError, ValueError, KeyError):
            return []

    def _stages(self) -> list[dict]:
        """The switchable stages of the selected workflow ({id, label, tip, default_on}), at most three."""
        for t in self._wf_templates():
            info = stage_info(t)
            if info:
                return info[:3]
        return []

    def _update_stage_scales(self, reset: bool = False):
        """The strength slider of a stage that is a LoRA: shown beside its checkbox, usable while the stage is on.
        `reset`: another workflow, the slider starts at the strength the workflow ships with."""
        stages = self._stages()
        for i, (sf, sc, lb) in enumerate(self.stage_scales):
            st = stages[i] if i < len(stages) else None
            if st is None or st.get("strength") is None:
                sf.grid_remove()
                continue
            if reset:
                self.v_sstr[i].set(min(1.0, st["strength"]))
            sf.grid()
            sc.configure(state="normal" if self.stage_vars[i].get() else "disabled")
            lb.configure(text=f"{float(self.v_sstr[i].get()):.2f}")

    def _stage_strengths(self) -> dict:
        """{stage node id: strength} of the stages that have a slider."""
        return {st["id"]: round(float(self.v_sstr[i].get()), 2) for i, st in enumerate(self._stages())
                if st.get("strength") is not None}

    def _stage_label(self) -> str:
        st = self._stages()
        return st[0]["label"] if st else ""

    def _on_feather(self, _value=None):
        v = round(float(self.v_feather.get()) * 2) / 2
        self.lbl_feather.configure(text="hard edge" if v <= 0 else f"{v:g} %")

    def _wf_has_upscale(self, name: str) -> bool:
        if name == BUILTIN:
            return False
        try:
            return any(has_upscale_slot(load_template(w)) for w in resolve(self.workflows_dir / name))
        except (OSError, ValueError, KeyError):
            return False

    def _wf_has_tag(self, tag: str) -> bool:
        """True when the selected workflow has a node titled pc:<tag> (the built-in graph has all of them)."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return True
        try:
            return any(tag in workflows_tags(n) for w in resolve(self.workflows_dir / wf)
                       for n in load_template(w).values() if isinstance(n, dict))
        except (OSError, ValueError, KeyError):
            return False

    def _couple_workflow(self):
        """Upscale / Refine only run with an upscale workflow and no other mode runs with one: the mode takes the
        right workflow along (and gives the previous one back)."""
        mode, wf = self.v_mode.get(), self.v_workflow.get()
        has = self._wf_has_upscale(wf)
        if mode in SCALE_MODES and not has:
            names = [n for n in self.cb_workflow["values"] if self._wf_has_upscale(n)]
            if not names:
                self._status("No upscale workflow in the workflows folder (flux3-klein-upscale.json).", error=True)
                return
            self._edit_wf = wf
            last = getattr(self, "_scale_wf", "")
            self.v_workflow.set(last if last in names else next((n for n in names if "flux3" in n), names[0]))
        elif mode not in SCALE_MODES and has:
            self._scale_wf = wf
            back = getattr(self, "_edit_wf", "")
            self.v_workflow.set(back if back in list(self.cb_workflow["values"]) and not self._wf_has_upscale(back) else BUILTIN)

    def _workflow_picked(self):
        """The Workflow list was used: an upscale workflow puts the window in Upscale, any other takes it out of it."""
        wf, mode = self.v_workflow.get(), self.v_mode.get()
        has = self._wf_has_upscale(wf)
        if has:
            self._scale_wf = wf
        else:
            self._edit_wf = wf
        if has and mode not in SCALE_MODES:
            self.v_mode.set("upscale")
            self._on_mode()
        elif not has and mode in SCALE_MODES:
            self.v_mode.set("inpaint")
            self._on_mode()
        else:
            self._on_workflow()
        self._sync_model()

    def _update_availability(self):
        """Grey out what has no effect in the current mode with the current workflow."""
        if not hasattr(self, "w_adv"):
            return
        mode = self._run_mode()
        scale = mode in SCALE_MODES
        masked = mode in ("inpaint", "remove", "reference", "outpaint")
        editor = self._ignores_mask()

        def on(widget, yes, normal="normal"):
            widget.configure(state=normal if yes else "disabled")

        on(self.w_denoise, not (mode == "txt2img" or editor or scale))
        on(self.w_variants, not scale)                       # the upscale workflow gives one picture
        on(self.w_adv["Base res."], not scale)               # the picture goes in at its own size
        on(self.w_adv["Context"], masked)
        on(self.w_adv["Mask grow"], masked and not editor)
        on(self.w_adv["Mask blur"], masked and not editor)
        on(self.cb_lm, mode != "upscale", "readonly")        # Upscale opens a new document: no layer to mask
        on(self.cb_cutout, self._ref_style() == "simple")     # the classic sentence has its own wording
        on(self.cb_collage, self._ref_style() == "classic")   # the simple style never pastes a rough copy
        on(self.t_neg, self._wf_has_tag("negative"))
        self.t_neg.configure(fg=FG if self._wf_has_tag("negative") else DISABLED)

    def _on_workflow(self):
        # a custom workflow carries its own model/steps/CFG/sampler – these fields apply to the built-in one only
        state = "normal" if self.v_workflow.get() == BUILTIN else "disabled"
        self._sync_sampler_fields()
        # Fooocus inpaint only exists in the built-in graph
        if state == "normal":
            self.cb_fooocus.grid()
        else:
            self.cb_fooocus.grid_remove()
        # the text model applies to custom workflows (nodes tagged pc:clip), not to the built-in graph, and only
        # while the prompt enhancement is on
        has_writer = self._has_text_model() and self.v_mode.get() not in ("reference", "remove")  # these modes: fixed instruction
        self.cb_enhance.configure(state="normal" if has_writer else "disabled")
        llm = next((m for m in (writer_model(t) for t in self._wf_templates()) if m), "")
        self.tt_enhance.text = ENHANCE_TIP + (f"\nText model: {llm}" if llm else "")
        name = next((n for n in (writer_name(t) for t in self._wf_templates()) if n), "")
        self.cb_enhance.configure(text="LLM prompt enhancement" + (f" ({name})" if name else ""))
        has_lora = self._has_lora_switch()
        self.cb_turbo.configure(state="normal" if has_lora else "disabled", text=self._lora_label())
        for w in (self.cb_turbo, self.f_lora):      # no LoRA of its own in this workflow: nothing to show (no greyed-out box)
            if has_lora:
                w.grid()
            else:
                w.grid_remove()
        if self.v_workflow.get() != self._lora_wf:   # another workflow: the slider starts at the value it ships with
            self._lora_wf = self.v_workflow.get()
            for t in self._wf_templates():
                d0 = lora_strength(t)
                if d0 is not None:
                    self.v_lora_str.set(min(1.0, d0))
                    self._on_lora_str()
                    break
        self.w_lora_str.configure(state="normal" if has_lora and self.v_turbo.get() else "disabled")
        tip = next((t for t in (lora_tip(x) for x in self._wf_templates()) if t), "")
        self.tt_turbo.text = tip or LORA_TIP
        stages = self._stages()
        reset_str = False
        if self.v_workflow.get() != self._stage_wf:   # another workflow: its stages start the way it says
            self._stage_wf = self.v_workflow.get()
            reset_str = True
            for var, st in zip(self.stage_vars, stages):
                var.set(st["default_on"])
        for i, cb in enumerate(self.stage_cbs):
            if i < len(stages):
                cb.configure(state="normal", text=stages[i]["label"])
                self.stage_tips[i].text = stages[i]["tip"] or STAGE_TIP
                cb.grid()
            else:
                cb.configure(state="disabled", text="Stage")
                cb.grid_remove()          # a workflow without that stage shows nothing (the stages belong to MOSS / Flux 3 upscale)
        self._update_stage_scales(reset=reset_str)
        self._update_options_box(has_lora, stages)
        self.w_detail.configure(state="normal" if self._run_mode() in SCALE_MODES else "disabled")
        enhancing = has_writer and bool(self.v_enhance.get())
        self.cb_clip.configure(state="readonly" if (state == "disabled" and enhancing) else "disabled")
        self._update_feather_state()
        self._update_availability()

    def _update_options_box(self, has_lora: bool, stages: list):
        """The box with the workflow's LoRA / stage switches is shown only when there is something in it."""
        want = bool(has_lora or stages)
        shown = bool(self.f_opts.winfo_manager())
        if want and not shown:
            self.f_opts.pack(fill="x", padx=10, pady=4, after=self.f_neg)
        elif not want and shown:
            self.f_opts.pack_forget()
        if want != shown and getattr(self, "_sized", False):
            self._fit_height()

    def _sync_sampler_fields(self):
        """Steps, CFG, Denoise (and sampler / scheduler) show what the selected workflow runs with - without its speed LoRA
        when that is switched off. Steps, CFG, sampler and scheduler can be changed (under Advanced)."""
        if self.v_workflow.get() == BUILTIN:
            self._wf_vals, self._vals_key = {}, None
            for w in self.recipe_widgets:
                w.configure(state="normal")
            return
        speed = bool(self.v_turbo.get()) or not self._has_lora_switch()
        key = (self.v_workflow.get(), speed)
        vals = {}
        for t in self._wf_templates():
            vals = sampler_values(t if speed else bypass_lora(t))
            if vals:
                break
        self._wf_vals = vals
        if key != self._vals_key:
            self._vals_key = key
            for var, k in ((self.v_steps, "steps"), (self.v_cfg, "cfg"), (self.v_denoise, "denoise"),
                           (self.v_sampler, "sampler"), (self.v_scheduler, "scheduler")):
                if k in vals:
                    try:
                        var.set(vals[k])
                    except (tk.TclError, ValueError):
                        pass
        for w in (self.w_steps, self.w_cfg):
            w.configure(state="normal" if "steps" in vals else "disabled")
        # Sampler and Scheduler can be changed (under Advanced); a workflow that sets one another way (Flux 2's scheduler) keeps it
        self.cb_sampler.configure(state="readonly" if "sampler" in vals else "disabled")
        self.cb_sched.configure(state="readonly" if "scheduler" in vals else "disabled")

    def _sampler_override(self) -> dict:
        """Steps / CFG the user typed over the workflow's own (only what differs from what the fields showed)."""
        out = {}
        try:
            if "steps" in self._wf_vals and int(self.v_steps.get()) != int(self._wf_vals["steps"]):
                out["steps"] = int(self.v_steps.get())
            if "cfg" in self._wf_vals and abs(float(self.v_cfg.get()) - float(self._wf_vals["cfg"])) > 1e-6:
                out["cfg"] = float(self.v_cfg.get())
        except (tk.TclError, ValueError):
            pass
        for key, var in (("sampler", self.v_sampler), ("scheduler", self.v_scheduler)):
            val = str(var.get() or "").strip()
            if key in self._wf_vals and val and val != str(self._wf_vals[key]):
                out[key] = val
        return out

    def _has_text_model(self) -> bool:
        """True when the selected workflow (or one of a group) contains a text model that writes the prompt."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return False
        try:
            return any(prompt_phase_nodes(load_template(w)) for w in resolve(self.workflows_dir / wf))
        except (OSError, ValueError, KeyError):
            return False

    def _lora_label(self) -> str:
        """The checkbox text: the workflow names its LoRA (pc_lora_label in the _meta of the pc:lora node)."""
        wf = self.v_workflow.get()
        if wf != BUILTIN:
            try:
                for w in resolve(self.workflows_dir / wf):
                    for nid in lora_switches(load_template(w)):
                        label = str(load_template(w)[nid].get("_meta", {}).get("pc_lora_label", "")).strip()
                        if label:
                            return label
            except (OSError, ValueError, KeyError):
                pass
        return "LoRA"

    def _has_lora_switch(self) -> bool:
        """True when the selected workflow (or one of a group) has a speed LoRA the window can switch off (pc:lora)."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return False
        try:
            return any(lora_switches(load_template(w)) for w in resolve(self.workflows_dir / wf))
        except (OSError, ValueError, KeyError):
            return False

    def _on_top(self):
        if not winlink.available():
            self.root.attributes("-topmost", bool(self.v_top.get()))
            return
        self.root.attributes("-topmost", False)   # owned window instead: above PhotoCraft only
        if getattr(self, "_link_job", None):
            self.root.after_cancel(self._link_job)
            self._link_job = None
        self._link_tries = 0
        if self.v_top.get():
            # not now: Tk's real window exists only once the event loop runs. After that the link is checked again
            # and again (watchdog): PhotoCraft's window may appear later, or Tk may rebuild its own.
            self._link_job = self.root.after(300, self._try_link)
        else:
            winlink.unlink(self.root)

    def _yield_popups(self):
        """PhotoCraft draws its menus inside its own window, so this window cannot be put below them. Instead (Windows):
        a click in PhotoCraft's menu bar hides this window while the menu is in use; it returns with the next click
        outside the menu bar, Escape or when the pointer leaves PhotoCraft (winlink.menu_step)."""
        self._popup_job = None
        if self.v_top.get() and winlink.available():
            self._menu_state = winlink.guard_menus(self.root, getattr(self, "_menu_state", {}), self.ui)
            self._popup_job = self.root.after(80, self._yield_popups)

    def _try_link(self):
        self._link_job = None
        if not self.v_top.get():
            return
        if winlink.link(self.root):
            self._link_tries = 0
            self._pc_seen, self._pc_gone = True, 0
            if not getattr(self, "_popup_job", None):
                self._popup_job = self.root.after(300, self._yield_popups)
        else:
            if getattr(self, "_pc_seen", False) and winlink.owner_present() is False:
                self._pc_gone = getattr(self, "_pc_gone", 0) + 1
                if self._pc_gone >= 2:       # PhotoCraft was closed: this window closes with it
                    self._quit()
                    return
            self._link_tries = getattr(self, "_link_tries", 0) + 1
            if self._link_tries == 20:
                self.v_status.set("PhotoCraft window not found - this window stays free until it appears")
        self._link_job = self.root.after(1500, self._try_link)

    def _on_destroy(self, e):
        if e.widget is not self.root or getattr(self, "_closing", False):
            return
        self._closing = True   # PhotoCraft closed: Windows destroys owned windows without asking
        try:
            self._save_state(self._request())
        except Exception:
            pass
        self.bridge.cancel()

    # ---------- connections ----------

    def refresh(self):
        def work():
            info = {}
            try:
                self.pc.close()
                p = self.pc.ping()
                info["pc"] = f"PhotoCraft ● ({p['documents']} doc.)"
            except PhotoCraftError as e:
                info["pc"] = "PhotoCraft ○"
                info["err"] = str(e)
            try:
                info["ckpts"] = self.comfy.checkpoints()
                info["samplers"] = self.comfy.samplers()
                info["clips"] = self.comfy.clips()
                info["loras"] = self.comfy.loras()
                info["scheds"] = self.comfy.schedulers()
                info["fooocus"] = self.comfy.fooocus_inpaint()
                info["comfy"] = "ComfyUI ●"
            except ComfyError as e:
                info["comfy"] = "ComfyUI ○"
                info.setdefault("err", str(e))
            self.events.put(("refresh", info))
        threading.Thread(target=work, daemon=True).start()

    def _apply_refresh(self, info):
        self.v_conn.set(f"{info['pc']}   {info['comfy']}")
        if info.get("ckpts") and self.v_ckpt.get() not in info["ckpts"]:
            self.v_ckpt.set(info["ckpts"][0])  # only used by the built-in graph; there is no picker any more
        if info.get("clips"):
            self.cb_clip["values"] = [CLIP_DEFAULT] + info["clips"]
            if self.v_clip.get() not in self.cb_clip["values"]:
                self.v_clip.set(CLIP_DEFAULT)
        if info.get("loras") is not None:
            self.all_loras = list(info["loras"])
        if info.get("samplers"):
            self.cb_sampler["values"] = info["samplers"]
        if info.get("scheds"):
            self.cb_sched["values"] = info["scheds"]
        if "fooocus" in info:
            ok = info["fooocus"] is not None
            self.cb_fooocus.configure(state="normal" if ok else "disabled",
                                      text="Fooocus inpaint (SDXL, as in Krita AI Diffusion)" + ("" if ok else " – not on server"))
        self.templates = list_templates(self.workflows_dir)
        self.cb_workflow["values"] = [BUILTIN] + [t.name for t in self.templates]
        if self.v_workflow.get() not in self.cb_workflow["values"]:
            self.v_workflow.set(BUILTIN)
        self._on_workflow()
        self._sync_model()
        if not self.v_model.get() and self.v_workflow.get() == BUILTIN:
            # nothing chosen yet (first start): open on the first model whose workflow is installed
            names = {t.name for t in self.templates}
            first = next((m for m in models.MODELS if set(m.workflows()) & names), None)
            if first:
                self.v_model.set(first.key)
                self._on_model()
        if info.get("err"):
            self._status(info["err"], error=True)

    # ---------- presets (save / load everything, incl. the prompt) ----------

    def _collect(self) -> dict:
        """Every setting in the window, as plain JSON values."""
        clip = self.v_clip.get().strip()
        return {
            "mode": self.v_mode.get(), "workflow": self.v_workflow.get(),
            "clip": "" if clip in ("", CLIP_DEFAULT) else clip,
            "checkpoint": self.v_ckpt.get().strip(), "steps": int(self.v_steps.get()), "cfg": float(self.v_cfg.get()),
            "denoise": float(self.v_denoise.get()), "seed": int(self.v_seed.get()), "variants": int(self.v_variants.get()),
            "sampler": self.v_sampler.get(), "scheduler": self.v_scheduler.get(),
            "base_res": int(self.v_res.get()), "context": float(self.v_context.get()),
            "mask_grow": int(self.v_grow.get()), "mask_blur": int(self.v_blur.get()), "overlap": int(self.v_overlap.get()),
            "scale": self._scale(), "ref_style": self._ref_style(),
            "fooocus": bool(self.v_fooocus.get()), "enhance": bool(self.v_enhance.get()),
            "turbo": bool(self.v_turbo.get()), "stage_on": bool(self.v_stage.get()), "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "loras": self._loras(), "sharpen": round(float(self.v_sharpen.get()), 2), "match": round(float(self.v_match.get()), 2), "detail": round(float(self.v_detail.get()), 2),
            "describe": bool(self.v_describe.get()), "describe_pos": self._desc_pos(), "describe_mp": self._desc_mp(),
            "lora_strength": round(float(self.v_lora_str.get()), 2), "ref_collage": bool(self.v_collage.get()), "ref_cutout": bool(self.v_cutout.get()),
            "layer_mask": {v: k for k, v in LAYER_MASKS.items()}.get(self.v_lmask.get(), "auto"),
            "feather_pct": round(float(self.v_feather.get()), 1),
            "prompt": self._prompt_text(), "negative": self.t_neg.get("1.0", "end").strip(),
        }

    def _apply_settings(self, s: dict) -> list[str]:
        """Put a saved preset into the window. Returns notes about anything that could not be applied."""
        notes: list[str] = []

        def put(var, key, conv=lambda v: v):
            if key in s:
                try:
                    var.set(conv(s[key]))
                except (tk.TclError, ValueError, TypeError):
                    notes.append(key)

        put(self.v_mode, "mode", str)
        wf = s.get("workflow")
        if wf is not None:
            if wf == BUILTIN or wf in list(self.cb_workflow["values"]):
                self.v_workflow.set(wf)
            else:
                notes.append(f"workflow {wf} not found")
        if "clip" in s:
            clip, known = s["clip"], list(self.cb_clip["values"])
            if not clip:
                self.v_clip.set(CLIP_DEFAULT)
            elif not known or clip in known:
                self.v_clip.set(clip)
            else:
                self.v_clip.set(CLIP_DEFAULT)
                notes.append(f"text model {clip} not found")
        put(self.v_ckpt, "checkpoint", str)
        put(self.v_steps, "steps", int)
        put(self.v_cfg, "cfg", float)
        put(self.v_denoise, "denoise", float)
        put(self.v_seed, "seed", int)
        put(self.v_variants, "variants", int)
        put(self.v_sampler, "sampler", str)
        put(self.v_scheduler, "scheduler", str)
        put(self.v_res, "base_res", int)
        put(self.v_context, "context", float)
        put(self.v_grow, "mask_grow", int)
        put(self.v_blur, "mask_blur", int)
        put(self.v_overlap, "overlap", int)
        put(self.v_scale, "scale", scale_text)
        put(self.v_fooocus, "fooocus", bool)
        put(self.v_enhance, "enhance", bool)
        put(self.v_turbo, "turbo", bool)
        if "loras" in s:
            self._set_loras(s["loras"])
        put(self.v_stage, "stage_on", bool)
        put(self.v_stage2, "stage2_on", bool)
        put(self.v_stage3, "stage3_on", bool)
        if any(k in s for k in ("stage_on", "stage2_on", "stage3_on")):
            self._stage_wf = self.v_workflow.get()
        if isinstance(s.get("stage_strengths"), list):
            for var, v in zip(self.v_sstr, s["stage_strengths"]):
                try:
                    var.set(float(v))
                except (TypeError, ValueError, tk.TclError):
                    pass
            self._update_stage_scales()
        put(self.v_detail, "detail", float)
        put(self.v_describe, "describe", bool)
        put(self.v_desc_pos, "describe_pos", lambda v: DESC_POS.get(v, DESC_POS["front"]))
        put(self.v_desc_mp, "describe_mp", desc_mp_text)
        put(self.v_sharpen, "sharpen", float)
        put(self.v_match, "match", float)
        self._on_sharpen()
        self._on_match()
        if "lora_strength" in s:
            self._lora_wf = self.v_workflow.get()
            put(self.v_lora_str, "lora_strength", float)
            self._on_lora_str()
        self._on_detail()
        put(self.v_collage, "ref_collage", bool)
        put(self.v_cutout, "ref_cutout", bool)
        put(self.v_refstyle, "ref_style", lambda v: REF_STYLES.get(v, REF_STYLES["classic"]))
        put(self.v_feather, "feather_pct", float)
        self._on_feather()
        if "layer_mask" in s:
            self.v_lmask.set(LAYER_MASKS.get(s["layer_mask"], LAYER_MASKS["auto"]))
        self._update_feather_state()
        for widget, key in ((self.t_prompt, "prompt"), (self.t_neg, "negative")):
            # an empty prompt in a preset means "not part of the preset": never wipe what was typed
            if str(s.get(key, "")).strip():
                widget.delete("1.0", "end")
                widget.insert("1.0", str(s[key]))
        self._on_mode_ui()
        self._on_workflow()
        self._sync_model()
        return notes

    def _preset_path(self, name: str) -> Path:
        return self.presets_dir / (preset_stem(name) + ".json")

    def refresh_presets(self, select: str | None = None):
        names = sorted(p.stem for p in self.presets_dir.glob("*.json")) if self.presets_dir.is_dir() else []
        self.cb_preset["values"] = names
        if select is not None:
            self.v_preset.set(select)
        elif self.v_preset.get() not in names:
            self.v_preset.set("")

    def save_preset(self):
        name = self.v_preset.get().strip()
        if not name:
            self.save_preset_as()
        else:
            self._write_preset(name)

    def save_preset_as(self):
        name = simpledialog.askstring("Save preset", "Preset name:", parent=self.root, initialvalue=self.v_preset.get())
        if not name or not name.strip():
            return
        if self._preset_path(name).exists() and preset_stem(name) != self.v_preset.get():
            if not messagebox.askyesno("Save preset", f"A preset named “{preset_stem(name)}” exists. Overwrite it?", parent=self.root):
                return
        self._write_preset(name)

    def _write_preset(self, name: str):
        try:
            settings = self._collect()
        except (tk.TclError, ValueError) as e:
            self._status(f"Invalid value, preset not saved: {e}", error=True)
            return
        stem = preset_stem(name)
        data = {"format": 1, "name": stem, "saved": datetime.now().isoformat(timespec="seconds"), "settings": settings}
        try:
            self.presets_dir.mkdir(parents=True, exist_ok=True)
            self._preset_path(stem).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            self._status(f"Could not save the preset: {e}", error=True)
            return
        self.refresh_presets(select=stem)
        self._status(f"Saved preset “{stem}”.")

    def load_preset(self, name: str):
        if not name:
            return
        try:
            data = json.loads(self._preset_path(name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self._status(f"Could not load the preset: {e}", error=True)
            return
        notes = self._apply_settings(data.get("settings", data) if isinstance(data, dict) else {})
        self._status(f"Loaded preset “{name}”." + (f" Not applied: {'; '.join(notes)}." if notes else ""))

    def delete_preset(self):
        name = self.v_preset.get().strip()
        if not name:
            return
        if not messagebox.askyesno("Delete preset", f"Delete the preset “{name}”?", parent=self.root):
            return
        try:
            self._preset_path(name).unlink()
        except OSError as e:
            self._status(f"Could not delete the preset: {e}", error=True)
            return
        self.refresh_presets(select="")
        self._status(f"Deleted preset “{name}”.")

    # ---------- generation ----------

    def _request(self) -> Request:
        wf = self.v_workflow.get()
        wf_path = None if wf == BUILTIN else str(self.workflows_dir / wf)
        p = GenParams(prompt=self.t_prompt.get("1.0", "end").strip(), negative=self.t_neg.get("1.0", "end").strip(),
                      checkpoint=self.v_ckpt.get().strip(), steps=int(self.v_steps.get()), cfg=float(self.v_cfg.get()),
                      sampler=self.v_sampler.get(), scheduler=self.v_scheduler.get(), seed=int(self.v_seed.get()),
                      denoise=1.0 if self.v_mode.get() == "txt2img" else float(self.v_denoise.get()))
        p.clip = "" if self.v_clip.get() in ("", CLIP_DEFAULT) else self.v_clip.get().strip()
        m = self._model()
        spec = m.modes.get(self.v_mode.get()) if m else None
        target = p.prompt if (self.v_mode.get() == "remove" and spec is not None and spec.remove_text) else ""
        return Request(mode=self._run_mode(), params=p, remove_target=target,
                       describe=bool(self.v_describe.get()) and self._run_mode() in SCALE_MODES, describe_pos=self._desc_pos(), describe_mp=self._desc_mp(), workflow=wf_path, base_res=int(self.v_res.get()),
                       context=float(self.v_context.get()), mask_grow=int(self.v_grow.get()),
                       mask_blur=int(self.v_blur.get()),
                       overlap=int(self.v_overlap.get()), variants=int(self.v_variants.get()),
                       fooocus=bool(self.v_fooocus.get()), enhance=bool(self.v_enhance.get()) and self.v_mode.get() != "outpaint",
                       turbo=bool(self.v_turbo.get()), scale=self._scale(),
                       lora_strength=(round(float(self.v_lora_str.get()), 2) if self._has_lora_switch() else None),
                       stage_on=bool(self.v_stage.get()) or not self._stage_label(), stages_off=self._stages_off(), stage_strengths=self._stage_strengths(), sampler_override=self._sampler_override(), doc_tag=self._doc_tag(), loras=[tuple(x) for x in self._loras()], sharpen=0.0 if self.v_mode.get() == "outpaint" else round(float(self.v_sharpen.get()), 2), match=round(float(self.v_match.get()), 2), detail=round(float(self.v_detail.get()), 2), ref_style=self._ref_style(), ref_collage=bool(self.v_collage.get()), ref_cutout=bool(self.v_cutout.get()),
                       layer_mask={v: k for k, v in LAYER_MASKS.items()}.get(self.v_lmask.get(), "auto"),
                       feather_pct=round(float(self.v_feather.get()) * 2) / 2)

    def _doc_tag(self) -> str:
        """Model and options for the name of an upscaled document: "Flux3Klein x1.5 SeedVR2 Restore0.8"."""
        m = self._model()
        parts = [re.sub(r'[\\/:*?"<>|]+', "", m.label) if m else "AI"]
        if self.v_mode.get() == "upscale":
            parts.append(f"x{self._scale():g}")
        for var, st in zip(self.stage_vars, self._stages()):
            if var.get():
                parts.append(st["label"].split()[0])
        if self._has_lora_switch() and self.v_turbo.get():
            try:
                parts.append(f"{self._lora_label().split()[0]}{float(self.v_lora_str.get()):.2g}")
            except (tk.TclError, ValueError):
                pass
        try:
            if self._run_mode() in SCALE_MODES and float(self.v_detail.get()) < 0.995:
                parts.append(f"mix{round(float(self.v_detail.get()) * 100)}")
        except (tk.TclError, ValueError):
            pass
        return " ".join(parts)

    def _layer_prefix(self) -> str:
        """The name the result layers start with (presets are hidden): "Qwen2.1 Fill", then " #<running number>"."""
        m = self._model()
        name, short = (m.label if m else "AI"), SHORT_MODES.get(self.v_mode.get(), self.v_mode.get())
        return name if name.endswith(" " + short) else f"{name} {short}"      # "Fibo 2.0 Edit" + Edit = "Fibo 2.0 Edit"

    def _stages_off(self) -> list[str]:
        """Node ids of the second and third switchable stage when their checkboxes are off (the first one is stage_on)."""
        st = self._stages()
        return [s["id"] for s, var in zip(st[1:], self.stage_vars[1:]) if not var.get()]

    def generate(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            req = self._request()
        except (tk.TclError, ValueError) as e:
            self._status(f"Invalid value: {e}", error=True)
            return
        req.preset = self._layer_prefix()
        if req.preset:   # running number per model and function, kept between sessions
            runs = dict(self.state.get("runs", {}))
            req.run_no = int(runs.get(req.preset, 0)) + 1
            runs[req.preset] = req.run_no
            self.state["runs"] = runs
        self._save_state(req)
        self.b_go.configure(state="disabled")
        self.b_undo.configure(state="disabled")
        self.b_redo.configure(state="disabled")
        self.b_stop.configure(state="normal")
        self._reset_progress()

        def progress(f, msg, phase="", phase_fraction=-1.0, elapsed=0.0):
            self.events.put(("progress", (f, msg, phase, phase_fraction, elapsed)))

        runs = sweep_requests(req, parse_list(self.v_cmp_res.get(), int), parse_list(self.v_cmp_ctx.get(), float))
        if len(runs) > 1:
            if req.params.seed is None or req.params.seed < 0:
                req.params.seed = random.randint(0, 2**31 - 1)   # one seed for the whole series: only the value differs

        def work():
            try:
                total = 0
                for k, rq in enumerate(runs):
                    if len(runs) > 1:
                        self.events.put(("progress", (0.0, f"Comparison {k + 1}/{len(runs)}: {rq.label}", "prepare", -1.0, 0.0)))
                    res = self.bridge.run(rq, progress)
                    total += len(res["layers"])
                self.events.put(("vgl", res.get("vgl", "")))
                self.events.put(("done", f"Done · seed {res['seed']} · {total} layer{'s' if total != 1 else ''}"))
            except Cancelled:
                self.events.put(("done", "Cancelled."))
            except (BridgeError, ComfyError, PhotoCraftError, ValueError, OSError) as e:
                self.events.put(("done", f"Error: {e}"))
            except Exception as e:  # unexpected – show it instead of dying silently
                self.events.put(("done", f"Unexpected error: {type(e).__name__}: {e}"))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def undo_edit(self):
        self._history_step(self.bridge.undo_last)

    def redo_edit(self):
        self._history_step(self.bridge.redo_last)

    def _history_step(self, fn):
        if self.worker and self.worker.is_alive():
            return
        self.b_undo.configure(state="disabled")
        self.b_redo.configure(state="disabled")

        def work():
            try:
                self.events.put(("note", fn()))
            except (BridgeError, PhotoCraftError) as e:
                self.events.put(("note-error", f"Error: {e}"))
            except Exception as e:
                self.events.put(("note-error", f"Unexpected error: {type(e).__name__}: {e}"))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def stop(self):
        if self.worker and self.worker.is_alive():
            self.bridge.cancel()
            self._status("Cancelling…")

    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "progress":
                    f, msg, phase, pf, elapsed = data
                    self._set_progress(f, msg, phase, pf, elapsed)
                    # the bar's label names the step, the line below it says nothing then (no second copy of the same words)
                    if msg and msg.startswith(("Comparison", "Object still")):
                        self._status(msg)
                    else:
                        self._status("")
                elif kind in ("note", "note-error"):
                    self._status(data, error=(kind == "note-error"))
                    self.b_undo.configure(state="normal")
                    self.b_redo.configure(state="normal")
                elif kind == "done":
                    ok = not data.startswith(("Error", "Cancel", "Unexpected"))
                    self._reset_progress(done=ok, text=data if ok else "")      # the success line sits above the bar, nothing below it
                    self._status("" if ok else data, error=data.startswith(("Error", "Unexpected")))
                    self.b_go.configure(state="normal")
                    self.b_undo.configure(state="normal")
                    self.b_redo.configure(state="normal")
                    self.b_stop.configure(state="disabled")
                elif kind == "vgl":
                    self._last_vgl = str(data or "")      # not shown in the window; the copy button next to the LLM checkbox takes it
                    for b in (self.b_copy, self.b_copy2):
                        b.configure(state="normal" if self._last_vgl.strip() else "disabled")
                elif kind == "refresh":
                    self._apply_refresh(data)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _reset_progress(self, done: bool = False, text: str = ""):
        self._bar_value = 1.0 if done else 0.0
        self.pb.configure(value=self._bar_value)
        self.v_pl.set((text or "Done") if done else "")      # clearly readable above the full bar; the line below adds the seed
        self._pl_style("Done.TLabel" if done else "Muted.TLabel")

    def _pl_style(self, style: str):
        lbl = getattr(self, "lbl_pl", None)
        if lbl is not None and getattr(self, "_pl_style_now", "") != style:
            self._pl_style_now = style
            lbl.configure(style=style)

    def _set_progress(self, fraction: float, msg: str | None, phase: str, phase_fraction: float, elapsed: float | None):
        """Move the single bar and name the step. Idempotent and only forward: Tk is touched only when the value or the
        text really changed (stop()/mode switches on the bar made it blink), and the bar never jumps back when a
        phase has no real progress (-1)."""
        secs = f"{elapsed:.0f} s" if elapsed is not None else ""
        if phase == "prompt":
            text = f"Expanding Prompt · {secs}"
        elif phase == "image":
            step = (msg or "").split("…")[0].strip()
            text = "Generating · " + (step if phase_fraction >= 0 and step else secs)
        elif phase == "place":
            text = "Placing the result"
        else:
            text = "Preparing"
        if self.v_pl.get() != text:
            self.v_pl.set(text)
        self._pl_style("Muted.TLabel")
        if fraction is not None and fraction > self._bar_value:
            self._bar_value = round(fraction, 3)
            self.pb.configure(value=self._bar_value)

    def _save_state(self, req: Request):
        p = req.params
        cfgmod.save_state({
            "mode": req.mode, "workflow": self.v_workflow.get(), "clip": p.clip, "checkpoint": p.checkpoint, "prompt": p.prompt,
            "negative": p.negative, "steps": p.steps, "cfg": p.cfg, "denoise": self.v_denoise.get(),
            "sampler": p.sampler, "scheduler": p.scheduler, "variants": req.variants, "base_res": req.base_res,
            "context": req.context, "mask_grow": req.mask_grow, "mask_blur": req.mask_blur, "overlap": req.overlap, "scale": req.scale,
            "preset": self.v_preset.get(), "on_top": bool(self.v_top.get()), "adv_open": bool(self.v_adv_open.get()), "model": self.v_model.get(), "neg_open": bool(self.v_neg_open.get()), "prompt_h": self._prompt_lines(), "fooocus": req.fooocus, "enhance": bool(self.v_enhance.get()), "turbo": req.turbo, "layer_mask": req.layer_mask,
            "stage_on": req.stage_on, "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "detail": req.detail, "describe": bool(self.v_describe.get()), "describe_pos": self._desc_pos(), "describe_mp": self._desc_mp(), "sharpen": round(float(self.v_sharpen.get()), 2), "match": req.match, "loras": [list(x) for x in req.loras], "lora_strength": req.lora_strength if req.lora_strength is not None else self.state.get("lora_strength", 1.0),
            "ref_collage": req.ref_collage, "ref_style": req.ref_style, "ref_cutout": req.ref_cutout, "runs": dict(self.state.get("runs", {})),
        })

    def _quit(self):
        self._closing = True
        try:
            self._save_state(self._request())
        except Exception:
            pass
        self.bridge.cancel()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_gui(cfg: dict) -> int:
    try:
        App(cfg).run()
    except tk.TclError as e:
        print(f"Can't open the window ({e}). Is the `tk` package installed?")
        return 1
    return 0
