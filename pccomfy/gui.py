"""Small bridge window (tkinter). Sits next to PhotoCraft: select in PhotoCraft, type the prompt here."""

from __future__ import annotations

import json
import os
import queue
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from . import config as cfgmod
from . import winlink
from .bridge import Bridge, BridgeError, Request, mask_is_used, prompt_phase_nodes
from .comfy import Cancelled, ComfyError, ComfyUI
from .photocraft import PhotoCraft, PhotoCraftError
from .workflows import GenParams, list_templates, load_template, resolve

MODE_LABELS = [
    ("inpaint", "Generative fill"),
    ("remove", "Remove"),
    ("reference", "Insert reference image"),
    ("outpaint", "Expand image"),
    ("img2img", "Image → image"),
    ("txt2img", "Text → image"),
]
MODE_TIPS = {
    "inpaint": "Select an area (Lasso / Rectangular Marquee), type what should appear there (\"a helicopter on the meadow\"), "
               "then Generate.\n"
               "A text is required with Fibo workflows. To take something away use \"Remove\".\n"
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
    "img2img": "Reworks the picture (or the selection) from your text.\n"
               "Checkpoint workflows: Denoise says how far it may change (low = stay close, high = new picture).\n"
               "Fibo workflows: type an instruction (\"make it night\"); no mask is needed.",
    "txt2img": "Creates a new image from text only, in the size of the selection or the whole canvas.\n"
               "Checkpoint workflows: describe the image.\n"
               "Fibo Edit workflows: only with \"enhance\" switched off (the text model needs a picture). "
               "Fibo Edit is made for editing, results may be arbitrary.",
}
BUILTIN = "Built-in (checkpoint)"
LAYER_MASKS = {"auto": "auto (recommended)", "soft": "soft (same as the model's)", "selection": "hard (from selection)", "none": "none"}

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

BG, PANEL, FG, MUTED, ACCENT = "#16181d", "#1f2229", "#e6e8ee", "#8a90a0", "#7c5cff"
ERROR, ERROR_TEXT = "#e5484d", "#ff8a8a"
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

        self.root = tk.Tk()
        self.root.title("PhotoCraft × ComfyUI")
        self.root.configure(bg=BG)
        self.root.minsize(MIN_W, 560)
        self._sized = False
        self._style()

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
        self.v_grow = tk.IntVar(value=g("mask_grow", d["mask_grow"]))
        self.v_blur = tk.IntVar(value=g("mask_blur", d["mask_blur"]))
        self.v_overlap = tk.IntVar(value=g("overlap", d["overlap"]))
        self.v_top = tk.BooleanVar(value=g("on_top", True))
        self.v_feather = tk.DoubleVar(value=g("feather_pct", 2.0))
        self.v_fooocus = tk.BooleanVar(value=g("fooocus", True))
        self.v_enhance = tk.BooleanVar(value=g("enhance", True))
        self.v_collage = tk.BooleanVar(value=g("ref_collage", True))
        self.v_lmask = tk.StringVar(value=LAYER_MASKS.get(g("layer_mask", "auto"), LAYER_MASKS["auto"]))
        self.v_status = tk.StringVar(value="Ready")
        self.v_conn = tk.StringVar(value="")

        self._build(d)
        self._on_mode()
        self._on_top()
        self._fit_height(MIN_W)
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
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor="#2c303a",
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, font=(FONT, 10))
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", foreground=MUTED, font=(FONT, 9))
        s.configure("Badge.TLabel", background=ERROR, foreground="white", font=(FONT, 10, "bold"))
        s.configure("Error.TLabel", foreground=ERROR_TEXT)
        s.configure("TLabelframe", background=BG, bordercolor="#2c303a")
        s.configure("TLabelframe.Label", background=BG, foreground=MUTED)
        s.configure("TRadiobutton", background=BG, foreground=FG)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        for w in ("TRadiobutton", "TCheckbutton"):
            s.map(w, background=[("active", BG)], indicatorbackground=[("selected", ACCENT), ("active", "#2a2e38")],
                  indicatorforeground=[("selected", "white")])
        s.configure("TButton", background=PANEL, foreground=FG, padding=6)
        s.map("TButton", background=[("active", "#2a2e38")])
        s.configure("Accent.TButton", background=ACCENT, foreground="white", font=(FONT, 10, "bold"))
        s.map("Accent.TButton", background=[("active", "#6a4cf0"), ("disabled", "#3a3550")])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
        s.configure("TCheckbutton", indicatorbackground=PANEL, indicatorforeground=FG)
        s.configure("TRadiobutton", indicatorbackground=PANEL)
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG)
        s.configure("Horizontal.TProgressbar", background=ACCENT)
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)

    def _text(self, parent, height):
        t = tk.Text(parent, height=height, width=10, wrap="word", bg=PANEL, fg=FG, insertbackground=FG,
                    relief="flat", highlightthickness=1, highlightbackground="#2c303a", highlightcolor=ACCENT,
                    font=(FONT, 10), padx=6, pady=4)
        return t

    def _spin(self, parent, var, frm, to, inc=1.0, width=6):
        return ttk.Spinbox(parent, textvariable=var, from_=frm, to=to, increment=inc, width=width)

    def _build(self, d):
        r = self.root
        pad = {"padx": 10, "pady": 4}

        pf = ttk.Frame(r)
        pf.pack(fill="x", **pad)
        pf.columnconfigure(1, weight=1)
        ttk.Label(pf, text="Preset").grid(row=0, column=0, sticky="w")
        self.cb_preset = ttk.Combobox(pf, textvariable=self.v_preset, state="readonly", width=8)
        self.cb_preset.bind("<<ComboboxSelected>>", lambda e: self.load_preset(self.v_preset.get()))
        self.cb_preset.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(pf, text="Save", width=6, command=self.save_preset).grid(row=0, column=2)
        ttk.Button(pf, text="Save as…", command=self.save_preset_as).grid(row=0, column=3, padx=(4, 0))
        ttk.Button(pf, text="Delete", width=7, command=self.delete_preset).grid(row=0, column=4, padx=(4, 0))

        mf = ttk.Frame(r)
        mf.pack(fill="x", **pad)
        mf.columnconfigure(1, weight=1)
        ttk.Label(mf, text="Workflow").grid(row=0, column=0, sticky="w")
        self.cb_workflow = ttk.Combobox(mf, textvariable=self.v_workflow, state="readonly", width=8)
        self.cb_workflow.bind("<<ComboboxSelected>>", lambda e: self._on_workflow())
        self.cb_workflow.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(mf, text="Text model").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.cb_clip = ttk.Combobox(mf, textvariable=self.v_clip, state="readonly", width=8)
        self.cb_clip.grid(row=1, column=1, sticky="ew", padx=6, pady=(4, 0))
        self.cb_enhance = ttk.Checkbutton(mf, text="LLM prompt enhancement", variable=self.v_enhance, command=self._on_workflow)
        self.cb_enhance.grid(row=2, column=1, sticky="w", padx=6, pady=(4, 0))
        Tooltip(self.cb_enhance, "On: the text model turns your instruction into the detailed prompt the image model expects "
                                 "(VGL for Fibo).\nOff: your text goes to the image model exactly as typed.\n"
                                 "Only for workflows that have a text model.")

        modes = ttk.Frame(r)
        modes.pack(fill="x", **pad)
        self.f_modes = modes
        for i, (key, label) in enumerate(MODE_LABELS):
            rb = ttk.Radiobutton(modes, text=label, value=key, variable=self.v_mode, command=self._on_mode)
            rb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=1)
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
        ttk.Label(r, text="Negative prompt").pack(anchor="w", padx=10, pady=(6, 0))
        self.t_neg = self._text(r, 2)
        self.t_neg.pack(fill="x", padx=10)
        self.t_neg.insert("1.0", self.state.get("negative", d["negative"]))

        sf = ttk.Frame(r)
        sf.pack(fill="x", **pad)
        items = [("Steps", self._spin(sf, self.v_steps, 1, 150, 1, 5)),
                 ("CFG", self._spin(sf, self.v_cfg, 1, 30, 0.5, 5)),
                 ("Denoise", self._spin(sf, self.v_denoise, 0.05, 1.0, 0.05, 5)),
                 ("Seed (-1 random)", self._spin(sf, self.v_seed, -1, 2**31 - 1, 1, 11)),
                 ("Variants", self._spin(sf, self.v_variants, 1, 8, 1, 4))]
        for i, (lbl, w) in enumerate(items):
            ttk.Label(sf, text=lbl, style="Muted.TLabel").grid(row=0, column=i, sticky="w", padx=(0, 6))
            w.grid(row=1, column=i, sticky="w", padx=(0, 6))
        self.w_denoise = items[2][1]
        self.recipe_widgets = [items[0][1], items[1][1]]

        sm = ttk.Frame(r)
        sm.pack(fill="x", **pad)
        sm.columnconfigure((1, 3), weight=1)
        ttk.Label(sm, text="Sampler", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.cb_sampler = ttk.Combobox(sm, textvariable=self.v_sampler, width=14)
        self.cb_sampler.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(sm, text="Scheduler", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.cb_sched = ttk.Combobox(sm, textvariable=self.v_scheduler, width=12)
        self.cb_sched.grid(row=0, column=3, sticky="ew", padx=6)
        self.recipe_widgets += [self.cb_sampler, self.cb_sched]

        self.f_out = ttk.LabelFrame(r, text="Expand image")
        ttk.Label(self.f_out, text="Extend the canvas with the Crop tool (confirm with Enter).\nThe empty area is filled.",
                  style="Muted.TLabel", justify="left", wraplength=280).grid(row=0, column=0, rowspan=2, sticky="w", padx=6, pady=(0, 6))
        ttk.Label(self.f_out, text="Overlap", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=6)
        self._spin(self.f_out, self.v_overlap, 0, 512, 8, 5).grid(row=1, column=1, padx=6, pady=(0, 6))
        self.f_out.columnconfigure(0, weight=1)

        self.f_ref = ttk.LabelFrame(r, text="Reference image")
        ttk.Label(self.f_ref, text="The top layer is the reference. Select where it should go.\nEverything below it is the picture.",
                  style="Muted.TLabel", justify="left", wraplength=360).pack(anchor="w", padx=6, pady=(0, 2))
        self.cb_collage = ttk.Checkbutton(self.f_ref, text="Rough placement in the picture", variable=self.v_collage)
        self.cb_collage.pack(anchor="w", padx=6, pady=(0, 6))
        Tooltip(self.cb_collage, "Pastes a rough, scaled copy of the reference into the selection of the picture the model "
                                 "sees, so it knows where the subject goes and how large it is. The model redraws it.\n"
                                 "Off: the model only gets the instruction (and where the selection lies in words).\n"
                                 "The text model is not used in this mode.")

        self.f_adv = ttk.LabelFrame(r, text="Advanced")
        self.f_adv.pack(fill="x", **pad)
        tips = {
            "Base res.": "Side (px) of the square whose area the model works at. Flux/Fibo/SDXL: 1024, SD 1.5: 512-768. "
                         "Higher = more detail but slower.",
            "Context": "How much of the surroundings the model sees around the selection, as a fraction of the selection's "
                       "longer side (0.4 = 40 %). More context fits the scene better, but the area you fill gets smaller in the crop.",
            "Mask grow": "Grows the mask the model gets by this many px so the generation overlaps the edge. Only for workflows "
                         "that use the mask (not Fibo, which regenerates the whole crop).",
            "Mask blur": "Softens the edge of the mask the model gets by this many px. Same as above: not used by Fibo.",
        }
        for i, (lbl, var, lo, hi, inc) in enumerate((("Base res.", self.v_res, 256, 2048, 64),
                                                    ("Context", self.v_context, 0, 2, 0.1),
                                                    ("Mask grow", self.v_grow, 0, 128, 2),
                                                    ("Mask blur", self.v_blur, 0, 128, 2))):
            lb = ttk.Label(self.f_adv, text=lbl, style="Muted.TLabel")
            lb.grid(row=0, column=i, sticky="w", padx=6)
            sp = self._spin(self.f_adv, var, lo, hi, inc, 6)
            sp.grid(row=1, column=i, padx=6, pady=(0, 6))
            Tooltip(lb, tips[lbl])
            Tooltip(sp, tips[lbl])
        self.cb_fooocus = ttk.Checkbutton(self.f_adv, text="Fooocus inpaint (SDXL, as in Krita AI Diffusion)", variable=self.v_fooocus)
        self.cb_fooocus.grid(row=2, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))
        Tooltip(self.cb_fooocus, "Only for the built-in inpaint graph with an SDXL checkpoint (Fooocus inpaint patch). "
                                 "Has no effect with a workflow such as the Fibo ones.")
        lm = ttk.Frame(self.f_adv)
        lm.grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 6))
        lb = ttk.Label(lm, text="Layer mask", style="Muted.TLabel")
        lb.pack(side="left")
        cb_lm = ttk.Combobox(lm, textvariable=self.v_lmask, values=list(LAYER_MASKS.values()), state="readonly", width=24)
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
        self.lbl_status = ttk.Label(st, textvariable=self.v_status, wraplength=380, justify="left")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        ttk.Label(r, text="Prompt written by the text model (VGL)", style="Muted.TLabel").pack(anchor="w", padx=10, pady=(6, 0))
        self.t_vgl = tk.Text(r, height=6, width=10, wrap="word", state="disabled", font=(FONT, 8))
        self.t_vgl.pack(fill="x", padx=10)
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

    def _on_mode_ui(self):
        mode = self.v_mode.get()
        if mode == "outpaint":
            self.f_out.pack(fill="x", padx=10, pady=4, after=self.f_modes)
        else:
            self.f_out.pack_forget()
        if mode == "reference":
            self.f_ref.pack(fill="x", padx=10, pady=4, after=self.f_modes)
        else:
            self.f_ref.pack_forget()
        self.w_denoise.configure(state="disabled" if mode == "txt2img" else "normal")
        self._sync_prompt_field(mode)
        self._update_feather_state()
        if self._sized:
            self._fit_height()

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

    def _fit_height(self, width: int | None = None):
        """Height to fit the content; the width stays (MIN_W at start, else what it is, e.g. after the user resized it)."""
        self.root.update_idletasks()
        self.root.geometry(f"{width or self.root.winfo_width()}x{max(560, self.root.winfo_reqheight())}")

    def _on_mode(self):
        self._on_mode_ui()
        self._on_workflow()  # the text model is not used in reference mode
        mode = self.v_mode.get()
        if mode in ("inpaint", "remove", "reference", "outpaint"):
            self.v_denoise.set(1.0)  # full denoise inside the mask; lower it to keep more of the original
        elif mode == "img2img" and self.v_denoise.get() >= 0.99:
            self.v_denoise.set(0.6)

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

    def _on_feather(self, _value=None):
        v = round(float(self.v_feather.get()) * 2) / 2
        self.lbl_feather.configure(text="hard edge" if v <= 0 else f"{v:g} % of the shorter side")

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
        enhancing = has_writer and bool(self.v_enhance.get())
        self.cb_clip.configure(state="readonly" if (state == "disabled" and enhancing) else "disabled")
        self._update_feather_state()

    def _has_text_model(self) -> bool:
        """True when the selected workflow (or one of a group) contains a text model that writes the prompt."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return False
        try:
            return any(prompt_phase_nodes(load_template(w)) for w in resolve(self.workflows_dir / wf))
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

    def _try_link(self):
        self._link_job = None
        if not self.v_top.get():
            return
        if winlink.link(self.root):
            self._link_tries = 0
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
            "fooocus": bool(self.v_fooocus.get()), "enhance": bool(self.v_enhance.get()),
            "ref_collage": bool(self.v_collage.get()),
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
        put(self.v_fooocus, "fooocus", bool)
        put(self.v_enhance, "enhance", bool)
        put(self.v_collage, "ref_collage", bool)
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
                       ref_collage=bool(self.v_collage.get()),
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
        self._save_state(req)
        self.b_go.configure(state="disabled")
        self.b_stop.configure(state="normal")
        self._reset_progress()

        def progress(f, msg, phase="", phase_fraction=-1.0, elapsed=0.0):
            self.events.put(("progress", (f, msg, phase, phase_fraction, elapsed)))

        def work():
            try:
                res = self.bridge.run(req, progress)
                self.events.put(("vgl", res.get("vgl", "")))
                self.events.put(("done", f"Done ({res['pipeline']}) – seed {res['seed']}, layers: {len(res['layers'])}"))
            except Cancelled:
                self.events.put(("done", "Cancelled."))
            except (BridgeError, ComfyError, PhotoCraftError, ValueError, OSError) as e:
                self.events.put(("done", f"Error: {e}"))
            except Exception as e:  # unexpected – show it instead of dying silently
                self.events.put(("done", f"Unexpected error: {type(e).__name__}: {e}"))
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
                elif kind == "done":
                    self._reset_progress(done=not data.startswith(("Error", "Cancel", "Unexpected")))
                    self._status(data, error=data.startswith(("Error", "Unexpected")))
                    self.b_go.configure(state="normal")
                    self.b_stop.configure(state="disabled")
                elif kind == "vgl":
                    self.t_vgl.configure(state="normal")
                    self.t_vgl.delete("1.0", "end")
                    self.t_vgl.insert("1.0", data)
                    self.t_vgl.configure(state="disabled")
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
            "context": req.context, "mask_grow": req.mask_grow, "mask_blur": req.mask_blur, "overlap": req.overlap,
            "preset": self.v_preset.get(), "on_top": bool(self.v_top.get()), "fooocus": req.fooocus, "enhance": req.enhance, "layer_mask": req.layer_mask,
            "ref_collage": req.ref_collage,
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
