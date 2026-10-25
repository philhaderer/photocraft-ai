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
from .workflows import GenParams, has_upscale_slot, list_templates, load_template, lora_strength, lora_switches, resolve, stage_switches

FILL_CONTEXT = 0.2   # Context (margin) that Generative fill starts with

MODE_LABELS = [
    ("inpaint", "Generative fill"),
    ("remove", "Remove"),
    ("reference", "Insert reference image"),
    ("outpaint", "Expand image"),
    ("edit", "Edit whole image"),
    ("img2img", "Image → image"),
    ("txt2img", "Text → image"),
    ("upscale", "Upscale (new file)"),
    ("refine", "Refine (same size)"),
]
MODE_TIPS = {
    "inpaint": "Select an area (Lasso / Rectangular Marquee), type what should appear there (\"a helicopter on the meadow\"), "
               "then Generate.\n"
               "A text is required with Fibo workflows. To take something away use \"Remove\".\n"
               "With Fibo the selection is drawn into the picture as a red outline and your text is wrapped in a fixed "
               "instruction (place it only inside the outline), so the object lands where you marked.\n"
               "With a text-model workflow and Enhance on, the text model writes the long prompt from it (about 25 s slower); otherwise it goes straight to Fibo.\n"
               "Fibo redraws the whole surrounding crop and ignores the mask, so the layer mask is off in \"auto\".",
    "remove": "Select the object to remove (tightly, but with the whole object inside), then Generate. No text needed.\n"
              "A red rectangle / outline is drawn into the picture the model gets (never into your document) and a fixed "
              "instruction says: erase everything inside it, every part of the subject, and paint the scenery behind.\n"
              "If the object is still there the plugin tries again by itself (up to 3 times, new seed each).\n"
              "If a part of the object is already gone, include what is left in the selection: Fibo likes to restore "
              "half-removed figures. Fibo workflows only.",
    "reference": "Insert a person or object with the look of a picture (e.g. a Viking).\n"
                 "1. Put it on its own layer ABOVE everything else (cut out, transparent).\n"
                 "2. Select where it should stand.\n3. Generate.\n"
                 "The top layer is the reference; all layers below are flattened in a temporary copy that is deleted again. "
                 "\"Rough placement\" pastes a scaled copy into the selection so the position is kept. "
                 "Your text is added to a fixed instruction (\"standing, facing left\"). Fibo workflows only.",
    "outpaint": "Extend the canvas with the Crop tool (confirm with Enter), then Generate: the empty area is filled.\n"
                "Text is optional and describes what the new area shows.\n"
                "Large extensions drift in style and tone at the seam: extend in smaller steps and repeat.",
    "edit": "Changes the WHOLE picture from your text, like talking to an image editor (\"make it night\", \"turn the car red\").\n"
            "A selection is ignored. Needs an edit workflow (Fibo, Qwen Image 2.1 Edit, Flux 2/3 Klein edit): use a preset.",
    "img2img": "Reworks the picture (or the selection) from your text.\n"
               "Checkpoint workflows: Denoise says how far it may change (low = stay close, high = new picture).\n"
               "Fibo workflows: type an instruction (\"make it night\"); no mask is needed.",
    "upscale": "Enlarges the picture (or the selection) by the factor and opens the result as a NEW document; your document stays "
               "as it is. Needs an upscale workflow (flux3-klein-upscale.json): SeedVR2 cleans the photo, Flux 3 Klein redraws it in tiles.\n"
               "The text is optional: a few words about what is in the picture (\"a young woman\") help the redraw.\n"
               "Results above 24 megapixels are refused.",
    "refine": "Cleans up and re-detail the picture (or the selection) at the SAME size and puts the result on a new layer.\n"
              "Same workflow as Upscale (flux3-klein-upscale.json), factor 1. The text is optional (a few words about the picture).",
    "txt2img": "Creates a new image from text only, in the size of the selection or the whole canvas.\n"
               "Checkpoint workflows: describe the image.\n"
               "Fibo Edit workflows: only with \"enhance\" switched off (the text model needs a picture). "
               "Fibo Edit is made for editing, results may be arbitrary.",
}
BUILTIN = "Built-in (checkpoint)"
LAYER_MASKS = {"auto": "auto (recommended)", "soft": "soft (same as the model's)", "selection": "hard (from selection)", "none": "none"}

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


def icon_image(root, kind: str, color: str):
    """A 16x16 icon for a button, drawn pixel by pixel: "save" (floppy disk), "saveas" (floppy with a plus), "trash"."""
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


MIN_W = 420  # the window opens at this width; text fields etc. stretch to it


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
        self.root.minsize(self._px(MIN_W), self._px(560))
        self._sized = False
        self._style()
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
        # Context is remembered per mode. Generative fill starts at 0.2: with a wide margin Fibo lets the new object grow
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
        self.v_scale = tk.StringVar(value=str(g("scale", 1.5)).removesuffix(".0"))
        self.v_top = tk.BooleanVar(value=g("on_top", True))
        self.v_feather = tk.DoubleVar(value=g("feather_pct", 2.0))
        self.v_fooocus = tk.BooleanVar(value=g("fooocus", True))
        self.v_enhance = tk.BooleanVar(value=g("enhance", True))
        self.v_turbo = tk.BooleanVar(value=g("turbo", True))
        self.v_lora_str = tk.DoubleVar(value=g("lora_strength", 1.0))
        self.v_model = tk.StringVar(value=g("model", ""))   # the tab; "" = a workflow of your own (everything enabled)
        self.v_sharpen = tk.DoubleVar(value=g("sharpen", 0.0))
        self.v_cmp_res = tk.StringVar(value="")
        self.v_cmp_ctx = tk.StringVar(value="")
        self.v_stage = tk.BooleanVar(value=g("stage_on", True))
        self.v_detail = tk.DoubleVar(value=g("detail", 1.0))
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
        s.configure("Icon.TButton", padding=4)
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
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG)
        s.configure("Horizontal.TProgressbar", background=ACCENT)
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
        cols = (len(models.MODELS) + 1) // 2
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
        ttk.Label(self.adv_body, text="Workflow", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.cb_workflow = ttk.Combobox(self.adv_body, textvariable=self.v_workflow, state="readonly", width=8)
        self.cb_workflow.bind("<<ComboboxSelected>>", lambda e: self._workflow_picked())
        self.cb_workflow.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(self.adv_body, text="Text model", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.cb_clip = ttk.Combobox(self.adv_body, textvariable=self.v_clip, state="readonly", width=8)
        self.cb_clip.grid(row=1, column=1, sticky="ew", padx=6, pady=(4, 0))
        pf = ttk.Frame(self.adv_body)
        pf.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
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

        sh = ttk.Frame(self.adv_body)
        sh.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        sh.columnconfigure(1, weight=1)
        ttk.Label(sh, text="Sharpen result", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.w_sharpen = ttk.Scale(sh, from_=0.0, to=1.0, variable=self.v_sharpen, command=self._on_sharpen)
        self.w_sharpen.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_sharpen = ttk.Label(sh, width=6, style="Muted.TLabel")
        self.lbl_sharpen.grid(row=0, column=2)
        Tooltip(self.w_sharpen, "A light sharpening of the finished result (0 = off). Helps models that come out slightly soft, "
                                "e.g. MOSS (tip: about 0.5).")
        self._on_sharpen()
        ttk.Label(self.adv_body, text="Compare base res", style="Muted.TLabel").grid(row=4, column=0, sticky="w", pady=(6, 0))
        e1 = ttk.Entry(self.adv_body, textvariable=self.v_cmp_res)
        e1.grid(row=4, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Label(self.adv_body, text="Compare context", style="Muted.TLabel").grid(row=5, column=0, sticky="w", pady=(4, 0))
        e2 = ttk.Entry(self.adv_body, textvariable=self.v_cmp_ctx)
        e2.grid(row=5, column=1, sticky="ew", padx=6, pady=(4, 0))
        for w in (e1, e2):
            Tooltip(w, "A test series: values separated by commas (1024, 1224, 1536 / 0.2, 0.4, 0.6). Generate then runs the "
                       "same request once per value with the SAME seed; every result is a layer named with its value.\n"
                       "Both filled = every combination.")
        self.cb_enhance = ttk.Checkbutton(mf, text="LLM prompt enhancement", variable=self.v_enhance, command=self._on_workflow)
        self.cb_enhance.grid(row=0, column=1, sticky="w", padx=6, pady=(4, 0))
        Tooltip(self.cb_enhance, "On: the text model turns your instruction into the detailed prompt the image model expects "
                                 "(VGL for Fibo).\nOff: your text goes to the image model exactly as typed.\n"
                                 "Only for workflows that have a text model.")
        self.cb_turbo = ttk.Checkbutton(mf, text="LoRA", variable=self.v_turbo)
        self.cb_turbo.grid(row=1, column=1, sticky="w", padx=6, pady=(4, 0))
        Tooltip(self.cb_turbo, "A LoRA of the workflow that can be switched off (the checkbox names it).\n"
                               "Qwen Image 2.1 - Turbo LoRA: on = about 10 steps; off = the full 25 steps, slower.\n"
                               "Flux 3 upscale - Restore LoRA: on = faces stay closer to the picture; off = plain Flux 3 Klein.\n"
                               "Flux 2 upscale - Ultra real LoRA: on = the realism LoRA at 0.3; off = plain Flux 2 Klein.\n"
                               "Greyed out when the workflow has no such LoRA.")

        self.f_lora = ttk.Frame(mf)    # strength of that LoRA
        self.f_lora.grid(row=2, column=1, sticky="ew", padx=6, pady=(2, 0))
        self.f_lora.columnconfigure(0, weight=1)
        self.w_lora_str = ttk.Scale(self.f_lora, from_=0.0, to=1.0, variable=self.v_lora_str, command=self._on_lora_str)
        self.w_lora_str.grid(row=0, column=0, sticky="ew")
        self.lbl_lora_str = ttk.Label(self.f_lora, width=14, style="Muted.TLabel")
        self.lbl_lora_str.grid(row=0, column=1, sticky="e", padx=(6, 0))
        Tooltip(self.w_lora_str, "How strong that LoRA works (0 = as if off, 1 = full). Starts at the value the workflow ships with.")
        self.cb_stage = ttk.Checkbutton(mf, text="Stage", variable=self.v_stage)
        self.cb_stage.grid(row=3, column=1, sticky="w", padx=6, pady=(2, 0))
        Tooltip(self.cb_stage, "A processing stage of the workflow that can be skipped (the checkbox names it).\n"
                               "Flux 3 upscale - SeedVR2: cleans the picture before Flux 3 redraws it. Off = Flux 3 works on the plainly "
                               "scaled picture (less of the SeedVR2 sharpness).")
        self._on_lora_str()

        modes = ttk.Frame(r)
        modes.pack(fill="x", **pad)
        self.f_modes = modes
        self.rb_modes = {}
        for i, (key, label) in enumerate(MODE_LABELS):
            rb = ttk.Radiobutton(modes, text=label, value=key, variable=self.v_mode, command=self._on_mode)
            rb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=1)
            self.rb_modes[key] = rb
            Tooltip(rb, MODE_TIPS[key])

        ff = ttk.Frame(r)
        ff.pack(fill="x", **pad)
        ff.columnconfigure(1, weight=1)
        lbl_f = ttk.Label(ff, text="Edge feather")
        lbl_f.grid(row=0, column=0, sticky="w")
        self.w_feather = sc = ttk.Scale(ff, from_=0, to=10, variable=self.v_feather, command=self._on_feather)
        sc.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_feather = ttk.Label(ff, width=22, style="Muted.TLabel")
        self.lbl_feather.grid(row=0, column=2, sticky="e")
        self._on_feather()
        for w in (lbl_f, sc):
            Tooltip(w, "How soft the edge of the new layer is, as a percentage of the selection's shorter side "
                       "(2 % is the default, 0 = hard edge).\nApplies to the layer mask the result is pasted with. "
                       "A feather you set in PhotoCraft (Weiche Kante) is kept as it is, this one is then ignored.\n"
                       "Greyed out when no soft layer mask is used (Layer mask: none / hard, or auto with a Fibo-type editor).")

        ttk.Label(r, text="Prompt").pack(anchor="w", padx=10)
        self.t_prompt = self._text(r, 4)
        self.t_prompt.pack(fill="x", padx=10)
        self.t_prompt.insert("1.0", self.state.get("prompt", ""))
        self.f_neg = ttk.Frame(r)
        self.f_neg.pack(fill="x", padx=10, pady=(6, 0))
        self.v_neg_open = tk.BooleanVar(value=bool(self.state.get("neg_open", False)))
        self.btn_neg = ttk.Button(self.f_neg, command=self._toggle_negative, style="Link.TButton")
        self.btn_neg.pack(anchor="w")
        self.neg_body = ttk.Frame(self.f_neg)
        self.t_neg = self._text(self.neg_body, 2)
        self.t_neg.pack(fill="x")
        self.t_neg.insert("1.0", self.state.get("negative", d["negative"]))

        mf.pack(fill="x", **pad)
        self.f_xl = ttk.Frame(r)       # extra LoRAs: a search box with a drop-down and a strength each
        self.f_xl.pack(fill="x", padx=10, pady=(2, 4))
        self.all_loras: list[str] = []
        self.lora_rows: list[dict] = []
        head = ttk.Frame(self.f_xl)
        head.pack(fill="x")
        ttk.Label(head, text="Extra LoRAs (style, detail ...)", style="Muted.TLabel").pack(side="left")
        self.b_addlora = ttk.Button(head, text="+ Add", style="Link.TButton", command=self._add_lora_row)
        self.b_addlora.pack(side="left", padx=8)
        Tooltip(self.b_addlora, "Adds a LoRA on top of the model's own ones. Type to search the list; the drop-down offers the LoRAs "
                                "of this model's folder first. Strength 0 to 1.5.")
        self.f_xl_rows = ttk.Frame(self.f_xl)
        self.f_xl_rows.pack(fill="x")
        sf = ttk.Frame(r)
        sf.pack(fill="x", **pad)
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
        self.recipe_widgets = [items[2][1], items[3][1]]

        sm = ttk.Frame(self.adv_body)
        sm.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        sm.columnconfigure((1, 3), weight=1)
        ttk.Label(sm, text="Sampler", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.cb_sampler = ttk.Combobox(sm, textvariable=self.v_sampler, width=14)
        self.cb_sampler.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(sm, text="Scheduler", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.cb_sched = ttk.Combobox(sm, textvariable=self.v_scheduler, width=12)
        self.cb_sched.grid(row=0, column=3, sticky="ew", padx=6)
        self.recipe_widgets += [self.cb_sampler, self.cb_sched]

        self.v_adv_open = tk.BooleanVar(value=bool(self.state.get("adv_open", False)))
        self.btn_adv = ttk.Button(self.f_adv, command=self._toggle_advanced, style="Link.TButton")
        self.btn_adv.pack(anchor="w")
        self.f_adv.pack(fill="x", padx=10, pady=4)
        self._show_advanced()
        self._show_negative()

        self.f_out = ttk.LabelFrame(r, text="Expand image")
        ttk.Label(self.f_out, text="Extend the canvas with the Crop tool (confirm with Enter).\nThe empty area is filled.",
                  style="Muted.TLabel", justify="left", wraplength=self._px(280)).grid(row=0, column=0, rowspan=2, sticky="w", padx=6, pady=(0, 6))
        ttk.Label(self.f_out, text="Overlap", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=6)
        self._spin(self.f_out, self.v_overlap, 0, 512, 8, 5).grid(row=1, column=1, padx=6, pady=(0, 6))
        self.f_out.columnconfigure(0, weight=1)

        self.f_scale = ttk.LabelFrame(r, text="Upscale")
        ttk.Label(self.f_scale, text="Factor per side (2 = four times the pixels). The result opens as a new document.",
                  style="Muted.TLabel", justify="left", wraplength=self._px(280)).grid(row=0, column=0, sticky="w", padx=6, pady=(0, 6))
        self.cb_scale = ttk.Combobox(self.f_scale, textvariable=self.v_scale, values=["1.5", "2", "3", "4"], width=5)
        self.cb_scale.grid(row=0, column=1, padx=6, pady=(0, 6))
        self.f_scale.columnconfigure(0, weight=1)
        self.f_detail = ttk.Frame(r)      # Upscale and Refine
        self.f_detail.columnconfigure(1, weight=1)
        ttk.Label(self.f_detail, text="Detail", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.w_detail = ttk.Scale(self.f_detail, from_=0.0, to=1.0, variable=self.v_detail, command=self._on_detail)
        self.w_detail.grid(row=0, column=1, sticky="ew", padx=8)
        self.lbl_detail = ttk.Label(self.f_detail, width=8, style="Muted.TLabel")
        self.lbl_detail.grid(row=0, column=2)
        Tooltip(self.w_detail, "How much of the new result is used. 100 % = all of it; less mixes in the plainly scaled original, "
                               "which tames a result that is too sharp or has odd textures.")
        self._on_detail()

        self.f_ref = ttk.LabelFrame(r, text="Reference image")
        ttk.Label(self.f_ref, text="The top layer is the reference. Select where it should go.\nEverything below it is the picture.",
                  style="Muted.TLabel", justify="left", wraplength=self._px(360)).pack(anchor="w", padx=6, pady=(0, 2))
        sty = ttk.Frame(self.f_ref)
        sty.pack(fill="x", padx=6, pady=(0, 4))
        lbs = ttk.Label(sty, text="Style", style="Muted.TLabel")
        lbs.pack(side="left")
        self.cb_refstyle = ttk.Combobox(sty, textvariable=self.v_refstyle, values=list(REF_STYLES.values()), state="readonly", width=38)
        self.cb_refstyle.pack(side="left", padx=6)
        self.cb_refstyle.bind("<<ComboboxSelected>>", lambda e: self._update_availability())
        for w in (lbs, self.cb_refstyle):
            Tooltip(w, "Two ways to tell Fibo what to do, to compare:\n"
                       "Classic: the reference is image_1, the picture image_2, a long fixed instruction (keep the subject exactly, "
                       "match the light), optional rough placement.\n"
                       "Simple: the picture is image1, the reference image2 and one sentence: \"Put the subject from image2 into "
                       "the <place> of the picture from image1.\" plus your text. No rough placement. Worked without cutting "
                       "the reference out.")
        self.cb_cutout = ttk.Checkbutton(self.f_ref, text="Cut out the reference (remove its background)", variable=self.v_cutout)
        self.cb_cutout.pack(anchor="w", padx=6, pady=(0, 4))
        Tooltip(self.cb_cutout, "Simple style: adds \"Remove the background of image2 first.\" to the sentence, so the reference "
                                "needs no cutting out beforehand.\nPlace the reference layer where it belongs (or select the "
                                "place): without a selection its position and size are the place.")
        self.cb_collage = ttk.Checkbutton(self.f_ref, text="Rough placement in the picture", variable=self.v_collage)
        self.cb_collage.pack(anchor="w", padx=6, pady=(0, 6))
        Tooltip(self.cb_collage, "Pastes a rough, scaled copy of the reference into the selection of the picture the model "
                                 "sees, so it knows where the subject goes and how large it is. The model redraws it.\n"
                                 "Off: the model only gets the instruction (and where the selection lies in words).\n"
                                 "The text model is not used in this mode.")

        self.f_img = ttk.LabelFrame(self.adv_body, text="Image and mask")
        self.f_img.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        tips = {
            "Base res.": "Side (px) of the square whose area the model works at. Flux/Fibo/SDXL: 1024, SD 1.5: 512-768. "
                         "Higher = more detail but slower.",
            "Context": "How much of the surroundings the model sees around the selection, as a fraction of the selection's "
                       "longer side (0.4 = 40 %). More context fits the scene better, but the area you fill gets smaller in the crop.",
            "Mask grow": "Grows the mask the model gets by this many px so the generation overlaps the edge. Only for workflows "
                         "that use the mask (not Fibo, which regenerates the whole crop).",
            "Mask blur": "Softens the edge of the mask the model gets by this many px. Same as above: not used by Fibo.",
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
        Tooltip(self.cb_fooocus, "Only for the built-in inpaint graph with an SDXL checkpoint (Fooocus inpaint patch). "
                                 "Has no effect with a workflow such as the Fibo ones.")
        lm = ttk.Frame(self.f_img)
        lm.grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))
        lb = ttk.Label(lm, text="Layer mask", style="Muted.TLabel")
        lb.pack(side="left")
        self.cb_lm = cb_lm = ttk.Combobox(lm, textvariable=self.v_lmask, values=list(LAYER_MASKS.values()), state="readonly", width=24)
        cb_lm.pack(side="left", padx=6)
        cb_lm.bind("<<ComboboxSelected>>", lambda e: self._update_feather_state())
        for w in (lb, cb_lm):
            Tooltip(w, "How the result is blended into your image.\n"
                       "auto: no mask for Fill with a Fibo-type editor (it regenerates the whole crop, so a mask would cut off\n"
                       "   what it changed on purpose, e.g. a person's shadow); soft for everything else - recommended.\n"
                       "soft: a feathered mask (see Edge feather).\n"
                       "hard (from selection): the selection exactly as PhotoCraft has it, incl. a feather you set there.\n"
                       "none: the whole generated area replaces the pixels, no mask.")

        bf = ttk.Frame(r)
        bf.pack(fill="x", padx=10, pady=(8, 2))
        self.b_go = ttk.Button(bf, text="Generate  (Ctrl+Enter)", style="Accent.TButton", command=self.generate)
        self.b_go.pack(side="left", fill="x", expand=True)
        self.b_stop = ttk.Button(bf, text="Cancel", command=self.stop, state="disabled")
        self.b_stop.pack(side="left", padx=(6, 0))
        self._icons.update({"undo": icon_image(self.root, "undo", FG), "redo": icon_image(self.root, "redo", FG)})
        self.b_undo = ttk.Button(bf, image=self._icons["undo"], style="Icon.TButton", command=self.undo_edit)
        self.b_undo.pack(side="left", padx=(6, 0))
        self.b_redo = ttk.Button(bf, image=self._icons["redo"], style="Icon.TButton", command=self.redo_edit)
        self.b_redo.pack(side="left", padx=(6, 0))
        Tooltip(self.b_redo, "Brings the AI edit back after an Undo (until the next generation).")
        Tooltip(self.b_undo, "Back to the state before the last generation in one click (a history snapshot taken at the start).\n"
                             "The history list shows every step the plugin made; this skips them all.")

        # one bar for the whole run (prompt, then image) with the current step written next to it
        self.v_pl = tk.StringVar(value="")
        row = ttk.Frame(r)
        row.pack(fill="x", padx=10, pady=(6, 0))
        ttk.Label(row, textvariable=self.v_pl, width=24, style="Muted.TLabel").pack(side="left")
        self.pb = ttk.Progressbar(row, mode="determinate", maximum=1.0)
        self.pb.pack(side="left", fill="x", expand=True)
        self._bar_value = 0.0
        st = ttk.Frame(r)
        st.pack(fill="x", padx=10, pady=(4, 0))
        self.lbl_err = ttk.Label(st, text="!", style="Badge.TLabel", width=2, anchor="center")
        self.lbl_status = ttk.Label(st, textvariable=self.v_status, wraplength=self._px(380), justify="left")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        foot = ttk.Frame(r)
        foot.pack(fill="x", side="bottom", padx=10, pady=6)
        ttk.Label(foot, textvariable=self.v_conn, style="Muted.TLabel").pack(side="left")
        ttk.Button(foot, text="Refresh", command=self.refresh).pack(side="left", padx=(8, 0))
        cb_top = ttk.Checkbutton(foot, text="Stay with PhotoCraft" if winlink.available() else "Always on top",
                                 variable=self.v_top, command=self._on_top)
        cb_top.pack(side="right")
        if winlink.available():
            Tooltip(cb_top, "On: this window belongs to PhotoCraft - it minimizes and returns with PhotoCraft, stays above "
                            "PhotoCraft only and does not cover other programs. It closes when PhotoCraft closes. "
                            "Off: a normal, free window.")

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
        if mode == "outpaint":
            self.f_out.pack(fill="x", padx=10, pady=4, after=self.f_modes)
        else:
            self.f_out.pack_forget()
        if mode == "upscale":
            self.f_scale.pack(fill="x", padx=10, pady=4, after=self.f_modes)
        else:
            self.f_scale.pack_forget()
        if mode in SCALE_MODES:
            self.f_detail.pack(fill="x", padx=10, pady=4, after=self.f_modes)
        else:
            self.f_detail.pack_forget()
        if mode == "reference":
            self.f_ref.pack(fill="x", padx=10, pady=4, after=self.f_modes)
        else:
            self.f_ref.pack_forget()
        self.w_denoise.configure(state="disabled" if mode == "txt2img" or self._ignores_mask() else "normal")   # an editor always runs at 1.0
        self._sync_prompt_field(mode)
        self._update_feather_state()
        self._update_availability()
        if self._sized:
            self._fit_height()

    def _ref_style(self) -> str:
        return {v: k for k, v in REF_STYLES.items()}.get(self.v_refstyle.get(), "simple")

    def _scale(self) -> float:
        try:
            return min(8.0, max(1.0, float(str(self.v_scale.get()).replace(",", "."))))
        except ValueError:
            return 2.0

    def _prompt_text(self) -> str:
        """The prompt to save: in Remove object the field is empty, the user's own text is kept aside."""
        if str(self.t_prompt.cget("state")) == "disabled":
            return getattr(self, "_prompt_kept", "")
        return self.t_prompt.get("1.0", "end").strip()

    def _sync_prompt_field(self, mode: str):
        """Remove object ignores the text: the field is emptied and greyed out, the typed text comes back afterwards."""
        t = self.t_prompt
        if mode == "remove":
            if str(t.cget("state")) != "disabled":
                self._prompt_kept = t.get("1.0", "end").strip()
                t.delete("1.0", "end")
                t.configure(state="disabled")
        elif str(t.cget("state")) == "disabled":
            t.configure(state="normal")
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
        cb = ttk.Combobox(row, textvariable=v_name, values=self._lora_choices())
        cb.grid(row=0, column=0, sticky="ew")
        cb.bind("<KeyRelease>", lambda e, c=cb, v=v_name: c.configure(values=self._lora_choices(v.get())))
        sp = ttk.Spinbox(row, textvariable=v_str, from_=0.0, to=1.5, increment=0.05, width=5)
        sp.grid(row=0, column=1, padx=4)
        rec = {"frame": row, "name": v_name, "strength": v_str, "combo": cb}
        rm = ttk.Button(row, text="x", style="Link.TButton", width=2, command=lambda: self._remove_lora_row(rec))
        rm.grid(row=0, column=2)
        Tooltip(rm, "Remove this LoRA")
        Tooltip(cb, "Type to search; the list shows this model's LoRAs first.")
        self.lora_rows.append(rec)
        self.b_addlora.configure(state="normal" if len(self.lora_rows) < self.LORA_MAX else "disabled")

    def _remove_lora_row(self, rec: dict):
        if rec in self.lora_rows:
            self.lora_rows.remove(rec)
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
        """Only what the chosen model does well can be picked; a model-less workflow of your own keeps everything."""
        m = self._model()
        for key, rb in self.rb_modes.items():
            if m is None:
                rb.grid()
                rb.configure(state="normal")
            elif key in m.modes:
                rb.grid()
                rb.configure(state="normal")
            elif key in ("img2img", "txt2img"):
                rb.grid_remove()           # nothing in the tabs uses these two
            else:
                rb.grid()
                rb.configure(state="disabled")

    def _on_model(self):
        """A tab was clicked: keep the mode when the model has it, else its first one; start with the model's settings."""
        m = self._model()
        if m is None:
            return
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
        keep = wf in m.workflows() and (wf == spec.workflow or wf in m.alt_workflows)
        s = dict(spec.settings)
        if not keep:
            s["workflow"] = spec.workflow
        self._switch_context(mode)   # first: the context memory belongs to the mode, the defaults below overwrite its value
        self._apply_settings(s)
        t = self.t_prompt
        cur = t.get("1.0", "end").strip() if str(t.cget("state")) != "disabled" else ""
        if cur in ("", models.PLACEHOLDER) and str(t.cget("state")) != "disabled":
            t.delete("1.0", "end")
            if spec.prompt_hint:
                t.insert("1.0", spec.prompt_hint)
        self._update_mode_radios()

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

    def _fit_height(self, width: int | None = None):
        """Height to fit the content; the width stays (MIN_W at start, else what it is, e.g. after the user resized it)."""
        self.root.update_idletasks()
        self.root.geometry(f"{width or self.root.winfo_width()}x{max(self._px(560), self.root.winfo_reqheight())}")

    def _on_mode(self):
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
        on = self._uses_soft_mask()
        self.w_feather.configure(state="normal" if on else "disabled")

    def _on_lora_str(self, _value=None):
        self.lbl_lora_str.configure(text=f"strength {float(self.v_lora_str.get()):.2f}")

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

    def _stage_label(self) -> str:
        for t in self._wf_templates():
            for _, label in stage_switches(t):
                return label
        return ""

    def _on_feather(self, _value=None):
        v = round(float(self.v_feather.get()) * 2) / 2
        self.lbl_feather.configure(text="hard edge" if v <= 0 else f"{v:g} % of the shorter side")

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
        mode = self.v_mode.get()
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
        for w in self.recipe_widgets:
            w.configure(state=state)
        # Fooocus inpaint only exists in the built-in graph
        if state == "normal":
            self.cb_fooocus.grid()
        else:
            self.cb_fooocus.grid_remove()
        # the text model applies to custom workflows (nodes tagged pc:clip), not to the built-in graph, and only
        # while the prompt enhancement is on
        has_writer = self._has_text_model() and self.v_mode.get() not in ("reference", "remove")  # these modes: fixed instruction
        self.cb_enhance.configure(state="normal" if has_writer else "disabled")
        has_lora = self._has_lora_switch()
        self.cb_turbo.configure(state="normal" if has_lora else "disabled", text=self._lora_label())
        if self.v_workflow.get() != self._lora_wf:   # another workflow: the slider starts at the value it ships with
            self._lora_wf = self.v_workflow.get()
            for t in self._wf_templates():
                d0 = lora_strength(t)
                if d0 is not None:
                    self.v_lora_str.set(min(1.0, d0))
                    self._on_lora_str()
                    break
        self.w_lora_str.configure(state="normal" if has_lora and self.v_turbo.get() else "disabled")
        stage = self._stage_label()
        self.cb_stage.configure(state="normal" if stage else "disabled", text=stage or "Stage")
        self.w_detail.configure(state="normal" if self.v_mode.get() in SCALE_MODES else "disabled")
        enhancing = has_writer and bool(self.v_enhance.get())
        self.cb_clip.configure(state="readonly" if (state == "disabled" and enhancing) else "disabled")
        self._update_feather_state()
        self._update_availability()

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
        """PhotoCraft's menus must not be hidden by this window: a few times a second it steps behind them."""
        self._popup_job = None
        if self.v_top.get() and winlink.available():
            winlink.yield_to_popups(self.root)
            self._popup_job = self.root.after(300, self._yield_popups)

    def _try_link(self):
        self._link_job = None
        if not self.v_top.get():
            return
        if winlink.link(self.root):
            self._link_tries = 0
            if not getattr(self, "_popup_job", None):
                self._popup_job = self.root.after(300, self._yield_popups)
        else:
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
            for r in self.lora_rows:
                r["combo"].configure(values=self._lora_choices())
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
            "turbo": bool(self.v_turbo.get()), "stage_on": bool(self.v_stage.get()), "loras": self._loras(), "sharpen": round(float(self.v_sharpen.get()), 2), "detail": round(float(self.v_detail.get()), 2),
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
        put(self.v_scale, "scale", lambda v: str(float(v)).removesuffix(".0"))
        put(self.v_fooocus, "fooocus", bool)
        put(self.v_enhance, "enhance", bool)
        put(self.v_turbo, "turbo", bool)
        if "loras" in s:
            self._set_loras(s["loras"])
        put(self.v_stage, "stage_on", bool)
        put(self.v_detail, "detail", float)
        put(self.v_sharpen, "sharpen", float)
        self._on_sharpen()
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
        return Request(mode=self.v_mode.get(), params=p, workflow=wf_path, base_res=int(self.v_res.get()),
                       context=float(self.v_context.get()), mask_grow=int(self.v_grow.get()),
                       mask_blur=int(self.v_blur.get()),
                       overlap=int(self.v_overlap.get()), variants=int(self.v_variants.get()),
                       fooocus=bool(self.v_fooocus.get()), enhance=bool(self.v_enhance.get()),
                       turbo=bool(self.v_turbo.get()), scale=self._scale(),
                       lora_strength=(round(float(self.v_lora_str.get()), 2) if self._has_lora_switch() else None),
                       stage_on=bool(self.v_stage.get()) or not self._stage_label(), loras=[tuple(x) for x in self._loras()], sharpen=round(float(self.v_sharpen.get()), 2), detail=round(float(self.v_detail.get()), 2), ref_style=self._ref_style(), ref_collage=bool(self.v_collage.get()), ref_cutout=bool(self.v_cutout.get()),
                       layer_mask={v: k for k, v in LAYER_MASKS.items()}.get(self.v_lmask.get(), "auto"),
                       feather_pct=round(float(self.v_feather.get()) * 2) / 2)

    def generate(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            req = self._request()
        except (tk.TclError, ValueError) as e:
            self._status(f"Invalid value: {e}", error=True)
            return
        req.preset = self.v_preset.get().strip()
        if req.preset:   # running number per preset, kept between sessions
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
                self.events.put(("done", f"Done ({res['pipeline']}) – seed {res['seed']}, layers: {total}"))
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
                    if msg:
                        self._status(msg)
                elif kind in ("note", "note-error"):
                    self._status(data, error=(kind == "note-error"))
                    self.b_undo.configure(state="normal")
                    self.b_redo.configure(state="normal")
                elif kind == "done":
                    self._reset_progress(done=not data.startswith(("Error", "Cancel", "Unexpected")))
                    self._status(data, error=data.startswith(("Error", "Unexpected")))
                    self.b_go.configure(state="normal")
                    self.b_undo.configure(state="normal")
                    self.b_redo.configure(state="normal")
                    self.b_stop.configure(state="disabled")
                elif kind == "vgl":
                    pass   # the text model's prompt is no longer shown in the window
                elif kind == "refresh":
                    self._apply_refresh(data)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _reset_progress(self, done: bool = False):
        self._bar_value = 1.0 if done else 0.0
        self.pb.configure(value=self._bar_value)
        self.v_pl.set("Done" if done else "")

    def _set_progress(self, fraction: float, msg: str | None, phase: str, phase_fraction: float, elapsed: float | None):
        """Move the single bar and name the step. Idempotent and only forward: Tk is touched only when the value or the
        text really changed (stop()/mode switches on the bar made it blink), and the bar never jumps back when a
        phase has no real progress (-1)."""
        secs = f"{elapsed:.0f} s" if elapsed is not None else ""
        if phase == "prompt":
            text = f"Prompt · {secs}"
        elif phase == "image":
            step = (msg or "").split("…")[0].strip()
            text = "Image · " + (step if phase_fraction >= 0 and step else secs)
        elif phase == "place":
            text = "Placing the result"
        else:
            text = "Preparing"
        if self.v_pl.get() != text:
            self.v_pl.set(text)
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
            "preset": self.v_preset.get(), "on_top": bool(self.v_top.get()), "adv_open": bool(self.v_adv_open.get()), "model": self.v_model.get(), "neg_open": bool(self.v_neg_open.get()), "fooocus": req.fooocus, "enhance": req.enhance, "turbo": req.turbo, "layer_mask": req.layer_mask,
            "stage_on": req.stage_on, "detail": req.detail, "sharpen": req.sharpen, "loras": [list(x) for x in req.loras], "lora_strength": req.lora_strength if req.lora_strength is not None else self.state.get("lora_strength", 1.0),
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
