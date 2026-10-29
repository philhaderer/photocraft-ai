"""The Tk window. App is assembled from the mixins in gui_*.py; this file keeps the start-up, the layout (_build) and the window handling."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _COMMON  # noqa: F401
from .gui_theme import ThemeMixin
from .gui_prompt import PromptMixin
from .gui_lora import LoraMixin
from .gui_modes import ModeMixin
from .gui_state import StateMixin
from .gui_run import RunMixin
from .ui_settings import SettingsMixin, GEAR_PX, FOOT_REFRESH_PADX, FOOT_RESET_PADX
from .refslots import RefSlotsMixin


class App(SettingsMixin, RefSlotsMixin, ThemeMixin, PromptMixin, LoraMixin, ModeMixin, StateMixin, RunMixin):
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
        self.v_feather = tk.DoubleVar(value=2.0)    # the function's own value is set after the build (see below)
        self.v_density = tk.IntVar(value=100)       # the same
        self.v_seam = tk.BooleanVar(value=False)    # seam correction A/B test: off at every start until confirmed (T2)
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
        self._vals_key = None                # (workflow, speed LoRA on) the steps / CFG / denoise fields were last read for
        self._wf_vals: dict = {}
        self._lora_wf = g("workflow", "")   # the workflow the LoRA strength slider was last set for
        self.v_lmask = tk.StringVar(value=LAYER_MASKS[layer_mask_key(g("layer_mask", "soft"))])
        self.v_status = tk.StringVar(value="Ready")
        self.v_conn = tk.StringVar(value="")

        self._build(d)
        self._set_loras(self.state.get("loras"))
        self._booting = True    # the saved window state is shown as it was: the model's starting settings are not applied
        self._on_mode()
        self._booting = False
        # the edge feather is not kept from the last time: every start has the function's own value (decision of the
        # user 28.10.; before, every start showed 2 % and Fibo Fill / Qwen Fill looked hard until the function was chosen again)
        spec = self._model().modes.get(self.v_mode.get()) if self._model() else None
        self.v_feather.set(float(spec.settings.get("feather_pct", 2.0)) if spec else 2.0)
        self._on_feather()
        self.v_density.set(int(spec.settings.get("mask_density", 100)) if spec else 100)
        self._on_density()
        self._on_top()
        self._fit_height(self._px(MIN_W))
        self._place_window()
        self._sized = True
        self.root.after(100, self._poll)
        self.root.after(200, self.refresh)
        self.refresh_presets()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.bind("<Destroy>", self._on_destroy, add="+")
        self.root.bind("<Configure>", self._remember_pos, add="+")

    def _build(self, d):
        r = self.root
        pad = {"padx": 10, "pady": 4}

        # the head: the functions first (big buttons with a symbol, two per row), the models below them (small outlined
        # chips, three per row; a model that cannot do the chosen function is greyed out). See docs/ux-funktion-zuerst.md.
        self.f_tabs = ttk.Frame(r)
        self.f_tabs.pack(fill="x", padx=10, pady=(8, 2))
        f_fn = self.f_modes = ttk.Frame(self.f_tabs)
        f_fn.pack(fill="x")
        for c in range(2):
            f_fn.columnconfigure(c, weight=1, uniform="fn")
        self.rb_modes = {}
        self.tt_modes = {}              # the tooltip of each function: the text of the selected model (see _update_mode_radios)
        for key, label in MODE_LABELS:
            rb = ttk.Radiobutton(f_fn, text=label, value=key, variable=self.v_mode, style="Tab.Toolbutton",
                                 image=self._function_icon(key), compound="left", command=self._on_mode)
            self.rb_modes[key] = rb
            self.tt_modes[key] = Tooltip(rb, models.function_tip(key, MODE_TIPS[key]))
        f_md = self.f_models = ttk.Frame(self.f_tabs)
        f_md.pack(fill="x", pady=(6, 0))
        cols = 3
        for c in range(cols):
            f_md.columnconfigure(c, weight=1, uniform="model")
        self.rb_tabs = {}
        self.tt_tabs = {}               # the tooltip of each model (the settings add what is missing, see ui_settings.py)
        for i, m in enumerate(models.MODELS):
            rb = ttk.Radiobutton(f_md, text=m.label, value=m.key, variable=self.v_model, style="Chip.Toolbutton",
                                 command=self._on_model)
            rb.grid(row=i // cols, column=i % cols, sticky="ew", padx=2, pady=2)
            self.tt_tabs[m.key] = Tooltip(rb, m.tip)
            self.rb_tabs[m.key] = rb

        # everything under the tabs: hidden while no model is chosen (ui_settings.py). It sits in a Canvas, so it can scroll
        # with a thin bar when the window would be taller than the screen (Advanced open, many slots): _fit_height decides.
        self.f_scrollbox = ttk.Frame(self.root)
        self.f_scrollbox.pack(fill="x")
        try:
            body_bg = ttk.Style().lookup("TFrame", "background") or BG
        except Exception:
            body_bg = BG
        self.cv_body = tk.Canvas(self.f_scrollbox, bg=body_bg, highlightthickness=0, bd=0)
        self.cv_body.pack(side="left", fill="both", expand=True)
        self.sb_body = ThinScrollbar(self.f_scrollbox, self.cv_body, self._px(6), body_bg)
        self.f_body = ttk.Frame(self.cv_body)
        self._body_win = self.cv_body.create_window(0, 0, window=self.f_body, anchor="nw")
        self.cv_body.bind("<Configure>", lambda e: self.cv_body.itemconfigure(self._body_win, width=e.width), add="+")
        self.f_body.bind("<Configure>", self._on_body_size, add="+")
        self.root.bind_all("<MouseWheel>", self.sb_body.wheel, add="+")
        r = self.f_body

        mf = ttk.Frame(r)
        mf.columnconfigure(1, weight=1)
        # Workflow and Text model live under "Advanced" (built below): the presets choose them.
        self.f_adv = ttk.Frame(r)
        self.adv_body = ttk.Frame(self.f_adv)
        self.adv_body.columnconfigure(1, weight=1)
        # the finishing options at the top of "Advanced settings": Sharpen, Match colours, Edge feather, Layer mask
        self.f_post = ttk.Frame(self.adv_body)
        self.f_post.grid(row=0, column=0, columnspan=2, sticky="ew")
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
        self._icons = {"save": self._icon("save"), "saveas": self._icon("saveas"), "delete": self._icon("trash", ERROR_TEXT)}
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
        self._icons["copy"] = self._icon("copy")
        self._last_vgl = ""             # the prompt the text model wrote in the last run
        self.b_copy = ttk.Button(self.f_enh, image=self._icons["copy"], style="Icon.TButton", command=self._copy_enhanced, state="disabled")
        self.b_copy.pack(side="left", padx=(8, 0))
        self.tt_copy = Tooltip(self.b_copy, "Copy the prompt the text model wrote in the last run.")
        self.cb_turbo = ttk.Checkbutton(mf, text="LoRA", variable=self.v_turbo)
        self.cb_turbo.grid(row=1, column=1, sticky="w", padx=6, pady=(4, 0))
        self.tt_turbo = Tooltip(self.cb_turbo, LORA_TIP)

        self.f_lora = ttk.Frame(mf)    # strength of that LoRA: on the right of its checkbox, like every slider
        self.f_lora.grid(row=1, column=2, sticky="e", pady=(4, 0))
        self.w_lora_str = Slider(self.f_lora, scale=self.ui, from_=0.0, to=1.0, variable=self.v_lora_str, command=self._on_lora_str,
                                 length=self._px(SLIDER_W))
        self.w_lora_str.grid(row=0, column=0)
        self.lbl_lora_str = ValueBox(self.f_lora, self.w_lora_str, self._on_lora_str)
        self.lbl_lora_str.grid(row=0, column=1, sticky="e", padx=(8, 0))
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
            sf.grid(row=3 + i, column=2, sticky="e", pady=(2, 0))
            sc = Slider(sf, scale=self.ui, from_=0.0, to=1.0, variable=self.v_sstr[i], length=self._px(SLIDER_W),
                        command=lambda _v=None: self._update_stage_scales())
            sc.pack(side="left")
            lb = ValueBox(sf, sc, lambda: self._update_stage_scales())
            lb.pack(side="left", padx=(8, 0))
            Tooltip(sc, "LoRA strength (0 = off, 1 = full).")
            sf.grid_remove()
            self.stage_scales.append((sf, sc, lb))
        self.cb_stage = self.stage_cbs[0]
        for cb in self.stage_cbs:
            cb.grid_remove()
        self._on_lora_str()

        self.f_opts = mf                # LoRA and stage switches of the workflow: shown only when it has some (_update_options_box)

        ff = ttk.Frame(self.f_post)     # shown only while a soft layer mask is used (see _update_feather_state)
        self.f_feather = ff
        self._slider_row(ff)
        lbl_f = ttk.Label(ff, text="Edge feather", style="Muted.TLabel")
        lbl_f.grid(row=0, column=0, sticky="w")
        self.w_feather = sc = Slider(ff, scale=self.ui, from_=0, to=10, variable=self.v_feather, command=self._on_feather,
                                     length=self._px(SLIDER_W))
        sc.grid(row=0, column=1, sticky="e", padx=8)
        self.lbl_feather = ValueBox(ff, sc, self._on_feather)
        self.lbl_feather.grid(row=0, column=2, sticky="e")
        self._on_feather()
        for w in (lbl_f, sc):
            Tooltip(w, "Softens the seam between the new area and your picture, in % of the selection's shorter side. 0 = hard edge.")

        fd = ttk.Frame(self.f_post)     # shown with Edge feather (see _update_feather_state)
        self.f_density = fd
        self._slider_row(fd)
        lbl_d = ttk.Label(fd, text="Mask density", style="Muted.TLabel")
        lbl_d.grid(row=0, column=0, sticky="w")
        self.w_density = sc = Slider(fd, scale=self.ui, from_=0, to=100, variable=self.v_density, command=self._on_density,
                                     length=self._px(SLIDER_W))
        sc.grid(row=0, column=1, sticky="e", padx=8)
        self.lbl_density = ValueBox(fd, sc, self._on_density)
        self.lbl_density.grid(row=0, column=2, sticky="e")
        self._on_density()
        for w in (lbl_d, sc):
            Tooltip(w, "How strongly the soft layer mask hides the redrawn area around your selection. "
                       "0 % = the whole redrawn area shows, 100 % = only the selection with its soft edge. "
                       "You can change it later in PhotoCraft's layer mask properties.")

        self.sep_prompt = ttk.Frame(r, style="Sep.TFrame", height=1)     # a light line above "Prompt"
        self.sep_prompt.pack(fill="x", padx=10, pady=(6, 4))
        self.f_ptop = ttk.Frame(r)      # "Prompt" and, where a mode has ready-made prompts, radio buttons that fill the field
        self.f_ptop.pack(fill="x", padx=10)
        ttk.Label(self.f_ptop, text="Prompt").pack(side="left")
        self._icons["clear"] = self._icon("trash")
        self.b_clear = ttk.Button(self.f_ptop, image=self._icons["clear"], style="Link.TButton", command=self._clear_prompt)   # flat: the row keeps its height
        self.b_clear.pack(side="right")
        Tooltip(self.b_clear, "Delete the prompt (Ctrl+Z in the field brings it back).")
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
        # fills its frame: with fill="x" only it was centred in a frame that still had the old height while the grip was
        # dragged, so its top edge jumped by half a line
        self.t_prompt.pack(side="left", fill="both", expand=True)
        self.grip = ttk.Frame(r, style="Grip.TFrame", height=self._px(7), cursor="sb_v_double_arrow")
        self.grip.pack(fill="x", padx=10, pady=(1, 0))
        self._grip_drag(self.grip, self.t_prompt)
        Tooltip(self.grip, "Drag to resize the prompt field.")
        self.lbl_hint = ttk.Label(r, text=EXPAND_HINT, style="Hint.TLabel", wraplength=self._px(MIN_W - 24), justify="left")   # Expand image, Upscale, Refine (see _update_prompt_hint)
        # Krea 2 / MOSS Expand: writes a description of the surroundings into the field (under the tip, user 29.10.)
        self.b_describe = ttk.Button(r, text="Describe", style="Small.TButton", command=self.describe_scene)
        Tooltip(self.b_describe, "Qwen 3.5 9B describes the surroundings of your picture (not the main subject) and writes "
                                 "it into the prompt. Edit it as you like.")
        self.t_prompt.insert("1.0", self.state.get("prompt", ""))
        self.f_sharp = ttk.Frame(self.f_post)     # a light sharpening of the finished result (under Advanced settings)
        self.f_sharp.pack(fill="x")
        self._slider_row(self.f_sharp)
        lb_sharp = ttk.Label(self.f_sharp, text="Sharpen result", style="Muted.TLabel")
        lb_sharp.grid(row=0, column=0, sticky="w")
        self.w_sharpen = Slider(self.f_sharp, scale=self.ui, from_=0.0, to=1.0, variable=self.v_sharpen, command=self._on_sharpen,
                                length=self._px(SLIDER_W))
        self.w_sharpen.grid(row=0, column=1, sticky="e", padx=8)
        self.lbl_sharpen = ValueBox(self.f_sharp, self.w_sharpen, self._on_sharpen, factor=100)
        self.lbl_sharpen.grid(row=0, column=2, sticky="e")
        Tooltip(self.w_sharpen, "Sharpens the finished result a little. 0 = off.")
        self._on_sharpen()
        self._sharp_widgets = (lb_sharp, self.w_sharpen, self.lbl_sharpen)   # hidden in Expand image
        lb_match = ttk.Label(self.f_sharp, text="Match colours", style="Muted.TLabel")
        lb_match.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.w_match = Slider(self.f_sharp, scale=self.ui, from_=0.0, to=1.0, variable=self.v_match, command=self._on_match,
                              length=self._px(SLIDER_W))
        self.w_match.grid(row=1, column=1, sticky="e", padx=8, pady=(2, 0))
        self.lbl_match = ValueBox(self.f_sharp, self.w_match, self._on_match, factor=100)
        self.lbl_match.grid(row=1, column=2, sticky="e", pady=(2, 0))
        self._match_widgets = (lb_match, self.w_match, self.lbl_match)   # shown only where the function can use them
        Tooltip(self.w_match, "Pulls the new area's saturation back towards its surroundings. 0 = off.")
        self._on_match()
        self.f_neg = ttk.Frame(r)
        self.f_neg.pack(fill="x", padx=10, pady=(6, 0))     # directly under the prompt
        self.f_enh.pack(fill="x", padx=10, pady=(6, 0))
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
        ttk.Label(head, text="Custom LoRAs:", style="Muted.TLabel").pack(side="left")
        self.b_addlora = ttk.Button(head, text="Add", image=self._icon("plus", MUTED), compound="left", style="Link.TButton",
                                    command=self._add_lora_row)
        self.b_addlora.pack(side="right")
        Tooltip(self.b_addlora, "Adds an extra LoRA (strength 0 to 1.5).")
        self.f_xl_rows = ttk.Frame(self.f_xl)
        self.f_xl_rows.pack(fill="x")
        sf = ttk.Frame(r)    # Seed and Variants: directly under the negative prompt
        sf.pack(fill="x", padx=10, pady=(6, 0), after=self.f_neg)
        self.f_sf = sf
        mf.pack(fill="x", padx=10, pady=4, after=self.f_neg)     # the LoRA / stage box: directly under the negative prompt
        af = ttk.Frame(self.adv_body)
        af.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        items = [("Seed (-1 random)", self._spin(sf, self.v_seed, -1, 2**31 - 1, 1, 11)),
                 ("Variants", self._spin(sf, self.v_variants, 1, 8, 1, 4)),
                 ("Steps", self._spin(af, self.v_steps, 1, 150, 1, 5)),
                 ("CFG", self._spin(af, self.v_cfg, 1, 30, 0.5, 5)),
                 ("Denoise", self._spin(af, self.v_denoise, 0.05, 1.0, 0.05, 5))]
        # Denoise is not shown (the user, 28.10.: "there is no use for it"): the widget stays ungridded, so the workflow's /
        # the function's value, presets, Reset and the requests work as before
        for i, (lbl, w) in enumerate(items):
            if lbl == "Denoise":
                continue
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
        self.sep_adv = ttk.Frame(self.f_adv, style="Sep.TFrame", height=1)     # a light line above "Advanced settings"
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
        self.f_detail = ttk.Frame(self.f_post)      # Upscale and Refine: under Advanced settings, above "Sharpen result" (user 28.10.)
        self._slider_row(self.f_detail)
        ttk.Label(self.f_detail, text="Mix Source/New Image", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.w_detail = Slider(self.f_detail, scale=self.ui, from_=0.0, to=1.0, variable=self.v_detail, command=self._on_detail,
                               length=self._px(SLIDER_W))
        self.w_detail.grid(row=0, column=1, sticky="e", padx=8)
        self.lbl_detail = ValueBox(self.f_detail, self.w_detail, self._on_detail, factor=100)
        self.lbl_detail.grid(row=0, column=2, sticky="e")
        Tooltip(self.w_detail, "100 % = only the new image; less mixes in the plain scaled original (tames over-sharp results).")
        self._on_detail()

        # "Image and mask" (Base res., Mask grow, Mask blur, Fooocus) is not shown (the user's choice, 28.10.): each model's
        # function sets these values; the widgets stay, so presets, Reset and the requests work as before
        self.f_img = ttk.LabelFrame(self.adv_body, text="Image and mask")
        tips = {
            "Base res.": "Size (px) the model works at. Higher = more detail, slower.",
            "Context": "How much of the surroundings the model sees around your selection, as a share of the selection's "
                       "longer side (0.4 = 40 % on each side). More often fits the new part better, but it takes longer.",
            "Mask grow": "Grows the model's mask by this many px (mask workflows only).",
            "Mask blur": "Softens the model's mask edge (mask workflows only).",
        }
        self.w_adv = {}
        self.l_adv = {}
        for i, (lbl, var, lo, hi, inc) in enumerate((("Base res.", self.v_res, 256, 2048, 64),
                                                    ("Mask grow", self.v_grow, 0, 128, 2),
                                                    ("Mask blur", self.v_blur, 0, 128, 2))):
            lb = ttk.Label(self.f_img, text=lbl, style="Muted.TLabel")
            lb.grid(row=0, column=i, sticky="w", padx=6)
            sp = self._spin(self.f_img, var, lo, hi, inc, 6)
            sp.grid(row=1, column=i, padx=6, pady=(0, 6))
            self.w_adv[lbl] = sp
            self.l_adv[lbl] = lb
            Tooltip(lb, tips[lbl])
            Tooltip(sp, tips[lbl])
        # Context: a slider like the others (0 to 1 in steps of 0.05), between Match colours and Edge feather (the user's
        # order, 28.10.); shown for Fill, Remove and Expand only (see _update_availability)
        fc = ttk.Frame(self.f_post)
        self.f_ctx = fc
        fc.pack(fill="x", pady=(2, 0))
        self._slider_row(fc)
        lb = ttk.Label(fc, text="Context", style="Muted.TLabel")
        lb.grid(row=0, column=0, sticky="w")
        sc = Slider(fc, scale=self.ui, from_=0.0, to=1.0, variable=self.v_context, command=self._on_context,
                    length=self._px(SLIDER_W))
        sc.grid(row=0, column=1, sticky="e", padx=8)
        self.lbl_context = ValueBox(fc, sc, self._on_context)
        self.lbl_context.grid(row=0, column=2, sticky="e")
        self.w_adv["Context"], self.l_adv["Context"] = sc, lb
        for w in (lb, sc):
            Tooltip(w, tips["Context"])
        try:
            self.v_context.trace_add("write", lambda *a: self._show_context())   # also after Reset, presets, a tab change
        except (AttributeError, tk.TclError):
            pass
        self._show_context()
        self.cb_fooocus = ttk.Checkbutton(self.f_img, text="Fooocus inpaint (SDXL, as in Krita AI Diffusion)", variable=self.v_fooocus)
        self.cb_fooocus.grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))
        Tooltip(self.cb_fooocus, "Built-in SDXL inpaint graph only.")
        lm = ttk.Frame(self.f_post)     # the last row of the finishing options (Advanced settings)
        self.f_lm = lm
        lm.pack(fill="x", pady=(2, 0))
        lb = ttk.Label(lm, text="Layer mask", style="Muted.TLabel")
        lb.pack(side="left")
        self.cb_lm = cb_lm = ttk.Combobox(lm, textvariable=self.v_lmask, values=list(LAYER_MASKS.values()), state="readonly", width=18)
        cb_lm.pack(side="left", padx=6)
        cb_lm.bind("<<ComboboxSelected>>", lambda e: self._update_feather_state())
        # beside the menu, with the dark background of a button; shown with Edge feather (see _update_feather_state)
        self.b_fprev = ttk.Button(lm, text="Show feather", style="Small.TButton", command=self.toggle_feather_preview)
        Tooltip(self.b_fprev, "Shows in PhotoCraft (in red) where the result will blend in, with this soft edge. "
                              "Click again, or Generate, to get your selection back.")
        for w in (lb, cb_lm):
            Tooltip(w, "How the result is blended into your picture: soft (soft edge), hard (the selection as it is), none (the whole redrawn area).")
        fs = self.f_seam = ttk.Frame(self.f_post)   # under Layer mask; Fill, Remove and Expand only (see _update_availability)
        fs.pack(fill="x", pady=(2, 0))
        self.cb_seam = ttk.Checkbutton(fs, text="Seam correction (A/B)", variable=self.v_seam)
        self.cb_seam.pack(side="left")
        Tooltip(self.cb_seam, "Evens out a lighter or darker rim where the result meets your picture. Test: each result "
                              "comes twice, “[seam fix]” on top and “[raw]” hidden below it.")

        bf = self.f_go = ttk.Frame(r)   # Generate, Cancel, Undo, Redo: above the line over "Prompt", under the functions
        bf.pack(fill="x", padx=10, pady=(6, 2), before=self.sep_prompt)
        self.b_go = ttk.Button(bf, text="Generate", width=11, style="Accent.TButton", command=self.generate)
        self.b_go.pack(side="left", fill="y")
        Tooltip(self.b_go, "Generate (Ctrl+Enter)")
        self.b_stop = ttk.Button(bf, text="Cancel", command=self.stop, state="disabled")
        self.b_stop.pack(side="left", fill="y", padx=(6, 0))
        self._icons.update({"undo": self._icon("undo"), "redo": self._icon("redo")})
        self.b_undo = ttk.Button(bf, image=self._icons["undo"], style="Icon.TButton", command=self.undo_edit)
        self.b_undo.pack(side="left", fill="y", padx=(6, 0))
        self.b_redo = ttk.Button(bf, image=self._icons["redo"], style="Icon.TButton", command=self.redo_edit)
        self.b_redo.pack(side="left", fill="y", padx=(6, 0))
        Tooltip(self.b_redo, "Brings the AI edit back after an Undo.")
        Tooltip(self.b_undo, "Back to the state before the last generation.")

        # one bar for the whole run (prompt, then image) with the current step written next to it
        self.v_pl = tk.StringVar(value="")
        self.sep_status = ttk.Frame(r, style="Sep.TFrame", height=1)     # a light line above the progress line, as above "Prompt"
        self.sep_status.pack(fill="x", padx=10, pady=(6, 0))
        row = ttk.Frame(r)
        row.pack(fill="x", padx=10, pady=(6, 0))
        top = self.f_pl_top = ttk.Frame(row)                  # above the bar, text on the left: shown only while it has text
        self.lbl_pl = ttk.Label(top, textvariable=self.v_pl, style="Muted.TLabel", anchor="w", justify="left")    # the step, or the green word "Done"
        self.lbl_pl.pack(side="left")
        self.v_pl_rest = tk.StringVar(value="")
        self.lbl_pl_rest = ttk.Label(top, textvariable=self.v_pl_rest, style="DoneRest.TLabel", anchor="w")      # after "Done": seed, layers, time
        self.lbl_pl_rest.pack(side="left")
        self.pb = ttk.Progressbar(row, mode="determinate", maximum=1.0)
        self.pb.pack(fill="x", pady=(2, 0))
        self._show_pl_line()
        self._bar_value = 0.0
        st = self.f_status = ttk.Frame(self.root)
        st.pack(fill="x", padx=10, pady=(4, 0))
        self.lbl_err = ttk.Label(st, text="!", style="Badge.TLabel", width=2, anchor="center")
        self.lbl_status = ttk.Label(st, textvariable=self.v_status, wraplength=self._px(MIN_W - 40), justify="left")
        self.lbl_status.pack(side="left", fill="x", expand=True)
        foot = ttk.Frame(self.root)
        foot.pack(fill="x", side="bottom", padx=10, pady=6)
        self.lbl_conn, self.lbl_dot = conn_status(foot)        # "ComfyUI ●": green = connected, red = not
        self.lbl_conn.pack(side="left")
        # Refresh = a flat circle arrow beside the dot, Reset = the text link "Defaults" (PLAN item 7, option A of the user 29.10.)
        b_refresh = self.b_refresh = ttk.Button(foot, image=self._icon("refresh", px=GEAR_PX), style="Link.TButton",
                                                command=self.refresh)
        b_refresh.pack(side="left", padx=FOOT_REFRESH_PADX)
        Tooltip(b_refresh, "Refresh: reads PhotoCraft's and ComfyUI's state again: connection, installed LoRAs, samplers, text models, workflows.")
        b_reset = self.b_reset = ttk.Button(foot, text="Defaults", style="Link.TButton", command=self.reset_settings)
        b_reset.pack(side="left", padx=FOOT_RESET_PADX)
        Tooltip(b_reset, "Back to the startup settings of this tab and function.")
        self._build_settings(foot)      # the gear at the right end of this row (ui_settings.py)

        for cb in (self.cb_scale, self.cb_lm, self.cb_sampler, self.cb_sched):
            self._open_on_click(cb)         # the list opens on a click anywhere in the box, not only on the arrow
        self._fit_job = None
        self.root.bind("<Configure>", self._on_content_size, add="+")      # the window follows its content: nothing hangs off the bottom
        self.root.bind("<Button-1>", self._lora_outside, add="+")
        self.root.bind("<Control-Return>", lambda e: (self.generate(), "break")[1])
        self.root.bind("<Escape>", lambda e: self.stop())

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

    def _place_window(self):
        """The window starts where it was last (saved in the state), if that is still on a screen. Otherwise it is placed
        at the first link: top right inside PhotoCraft, under its menu bar (winlink.first_position)."""
        self._placed = False
        self._win_pos = None
        pos = self.state.get("win_pos")
        try:
            x, y = int(pos[0]), int(pos[1])
        except (TypeError, ValueError, IndexError):
            return
        if winlink.on_screen(x + self._px(40), y + self._px(10)) is False:    # the title bar must be reachable
            return
        self.root.geometry(f"+{x}+{y}")
        self._win_pos = (x, y)
        self._placed = True
        self._checked_band = False

    def _place_at_owner(self):
        """Called once PhotoCraft's window is known: a first start goes to its top right corner; a saved position that
        lies in its menu bar moves just below it."""
        rect = winlink.owner_rect()
        if rect is None:
            return
        w = self.root.winfo_width()
        if not getattr(self, "_placed", True):
            x, y = winlink.first_position(rect, w, self.ui)
        elif not getattr(self, "_checked_band", True) and self._win_pos:
            x, y = winlink.below_menu_bar(self._win_pos, w, rect, self.ui)
        else:
            return
        self._placed, self._checked_band = True, True
        if (x, y) != self._win_pos:
            self.root.geometry(f"+{x}+{y}")
            self._win_pos = (x, y)

    def _remember_pos(self, e=None):
        """Keeps the window's place for the next start (saved with the state)."""
        if e is not None and e.widget is not self.root:
            return
        try:
            if self.root.state() != "normal":
                return
            m = re.match(r"\d+x\d+([+-]-?\d+)([+-]-?\d+)", self.root.geometry())
        except tk.TclError:
            return
        if m:
            x, y = int(m.group(1).replace("+", "")), int(m.group(2).replace("+", ""))
            if x > -10000 and y > -10000:       # a minimized window reports -32000
                self._win_pos = (x, y)

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
            self._place_at_owner()
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

    def _dialog(self, fn, **kw):
        """A Windows dialog (file picker ...) owned by this window. The link watchdog and the menu guard pause while it is
        open: re-linking this owned window under the dialog made Tk redraw it (the window showed twice, garbled)."""
        for name in ("_link_job", "_popup_job"):
            job = getattr(self, name, None)
            if job:
                self.root.after_cancel(job)
                setattr(self, name, None)
        try:
            return fn(parent=self.root, **kw)
        finally:
            if self.v_top.get() and winlink.available() and not getattr(self, "_closing", False):
                self._link_job = self.root.after(300, self._try_link)    # links again and restarts the menu guard

    def _on_destroy(self, e):
        if e.widget is not self.root or getattr(self, "_closing", False):
            return
        self._closing = True   # PhotoCraft closed: Windows destroys owned windows without asking
        try:
            self._save_state(self._request())
        except Exception:
            pass
        self.bridge.cancel()

    def _quit(self):
        self._closing = True
        try:
            self._save_state(self._request())
        except Exception:
            pass
        self.bridge.cancel()
        if self.bridge.feather_shown and not (self.worker and self.worker.is_alive()):
            try:    # the user's selection comes back before the window goes
                self.bridge.hide_feather()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_gui(cfg: dict) -> int:
    from . import autostart
    # held while the window is open: the autostart watcher does not open a second one (a .bat started this one)
    _mutex = autostart.hold_mutex(autostart.GUI_MUTEX)  # noqa: F841  (kept for the life of the window)
    try:
        App(cfg).run()
    except tk.TclError as e:
        print(f"Can't open the window ({e}). Is the `tk` package installed?")
        return 1
    return 0
