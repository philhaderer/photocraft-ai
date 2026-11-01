"""Easy Mode in the window (PLAN.md point 17): the switch in the header, hiding what Easy Mode does not show, the model the
plugin picks for each function. The logic without Tk is in easymode.py. Switched off, the window behaves as before."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from PIL import Image

from . import easymode as em, icons
from .gui_theme import ICON_PX
from .ui_downloads import browser_only, size_text
from .ui_settings import FOOT_RESET_PADX, SET_STYLES


class EasyMixin:
    # ---------- building ----------

    def _build_easy(self):
        """The switch (left of the clock) and the model label in the footer. Called at the end of _build."""
        self.b_easy = ttk.Checkbutton(self.f_header, text=em.SWITCH_TEXT, variable=self.v_easy, command=self.toggle_easy,
                                      style="Switch.Toolbutton", image=self._switch_icon(), compound="left")
        self.b_easy.pack(side="right", padx=(0, 8))
        Tooltip(self.b_easy, em.SWITCH_TIP)
        self.v_easy_model = tk.StringVar(value="")
        # the model Easy Mode uses: in the footer, right of "Live preview" (user 1.11.; no line under the function buttons)
        self.lbl_easy_model = ttk.Label(self.f_foot, textvariable=self.v_easy_model, style="Muted.TLabel")
        Tooltip(self.lbl_easy_model, em.MODEL_TIP)

    def _switch_icon(self):
        """The switch icon: grey while Easy Mode is off, orange while it is on (the button itself stays flat), with 2 px of
        extra room on its right (user 31.10.)."""
        cache = self.__dict__.setdefault("_icon_cache", {})

        def img(kind, c):
            if ("easy", kind, c) not in cache:
                px = self._px(ICON_PX)
                wide = Image.new("RGBA", (px + self._px(2), px), (0, 0, 0, 0))
                wide.paste(icons.render(kind, c, px), (0, 0))
                cache[("easy", kind, c)] = icons.photo(self.root, None, c, px, image=wide)
            return cache[("easy", kind, c)]
        return (img("toggle", MUTED), "selected", img("toggle-on", ACCENT))

    def _easy_boot(self):
        """At start: Easy Mode was left on. The saved window is shown as it was; the model is checked when ComfyUI's files are known."""
        if getattr(self, "_easy", False):
            self._easy_hide()

    # ---------- the choice of the model ----------

    def _easy_models(self) -> dict:
        """Each Easy Mode function -> the model Easy Mode would use now ('' = none, the button is greyed out)."""
        hidden = cfgmod.hidden_tabs()
        out = {}
        for mode in em.EASY_MODES:
            out[mode] = em.best_model(mode, lambda k, mode=mode: self._model_usable(k, mode), hidden)
        return out

    def _easy_refresh(self):
        """Easy Mode is on and something changed (ComfyUI's files, a loaded run): the function and model are a valid pair again."""
        if not getattr(self, "_easy", False) or getattr(self, "_easy_busy", False) or getattr(self, "_booting", False):
            return
        self._easy_busy = True
        try:
            picks = self._easy_models()
            mode = self.v_mode.get()
            changed = False
            if not picks.get(mode):
                nxt = next((m for m in em.EASY_MODES if picks[m]), "")
                if nxt:
                    mode, changed = nxt, True
                    self.v_mode.set(mode)
            key = picks.get(mode, "")
            if key and (changed or key != self.v_model.get()):
                self.v_model.set(key)
                self._on_model()
            self._update_mode_radios()
            self._apply_start_state()
            self._easy_hide()
        finally:
            self._easy_busy = False

    def _on_mode(self):
        if getattr(self, "_easy", False) and not getattr(self, "_booting", False):
            key = self._easy_models().get(self.v_mode.get(), "")
            if key and key != self.v_model.get():
                self.v_model.set(key)
                self._on_model()
                return
        super()._on_mode()

    def _remember_model_for_mode(self):
        if not getattr(self, "_easy", False):        # Easy Mode keeps no "model last used for this function"
            super()._remember_model_for_mode()

    def _below_prompt(self):
        if getattr(self, "_easy", False):
            return self.f_hint if self.f_hint.winfo_manager() else self.grip
        return super()._below_prompt()

    # ---------- showing and hiding ----------

    def _easy_hide(self):
        """Everything between the prompt and the status line goes (also the negative prompt), the model chips and the
        footer's "Reset page"; Upscale factor, Generate, the bars and the preview stay."""
        if not getattr(self, "_easy", False) or not hasattr(self, "lbl_easy_model"):     # (not built yet while the window is built)
            return
        for w in (self.f_neg, self.f_enh, self.f_opts, self.f_adv, self.b_describe, self.f_models, self.b_llm, self.f_pchoice,
                  self.b_reset):
            w.pack_forget()
        self.b_styles.pack_forget()      # (comes back through _update_styles_button)
        self._styles_shown = False
        mode = self.v_mode.get()
        picks = self._easy_models()
        key = picks.get(mode) or self.v_model.get()
        line = em.model_line(key) if key else ""
        self.v_easy_model.set(line or em.NO_MODELS)
        if not self.lbl_easy_model.winfo_manager():
            self.lbl_easy_model.pack(side="left", padx=FOOT_RESET_PADX, after=self.cb_live)

    def _easy_show(self):
        """Easy Mode is off: the hidden parts go back to their places (stacking order: negative prompt, LLM row, Upscale factor,
        LoRA switches, Advanced settings), then the normal methods set what belongs to the function."""
        self.lbl_easy_model.pack_forget()
        self.f_models.pack(fill="x", pady=(6, 0))
        for w in (self.f_scale, self.f_opts, self.f_enh):
            w.pack_forget()
        self.f_neg.pack(fill="x", padx=10, pady=(6, 0), before=self.sep_status)
        self.f_adv.pack(fill="x", padx=10, pady=4, before=self.sep_status)
        self.b_llm.pack(side="right", padx=(0, 6))
        self._update_styles_button()
        self.f_pchoice.pack(side="left", padx=(10, 0))
        self.b_reset.pack(side="left", padx=FOOT_RESET_PADX, before=self.cb_live)

    def _update_mode_radios(self):
        super()._update_mode_radios()
        if not getattr(self, "_easy", False):
            return
        picks = self._easy_models()
        shown = [k for k, _label in MODE_LABELS if k in em.EASY_MODES and k in self.rb_modes]     # the window's usual order
        for key, rb in self.rb_modes.items():
            if key not in shown:
                rb.grid_remove()
        for i, key in enumerate(shown):
            rb = self.rb_modes[key]
            rb.grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
            rb.configure(state="normal" if picks[key] else "disabled")
            self.tt_modes[key].text = MODE_TIPS[key] if picks[key] else em.MODE_GREYED_TIP     # no "Ranking:" line in Easy Mode

    def _show_enhance_box(self, on: bool):
        if not getattr(self, "_easy", False):
            super()._show_enhance_box(on)

    def _update_options_box(self, has_lora: bool, stages: list):
        if not getattr(self, "_easy", False):
            super()._update_options_box(has_lora, stages)

    def _apply_start_state(self, fit: bool = True):
        super()._apply_start_state(fit)
        if getattr(self, "_easy", False):
            if self.start_state():
                self.v_empty.set(em.NO_MODELS)
            self._easy_hide()
            if fit and getattr(self, "_sized", False):
                self._fit_height()

    def start_state(self) -> str:
        state = super().start_state()
        return "" if (getattr(self, "_easy", False) and state == "choose") else state    # Easy Mode picks the model itself

    def _update_prompt_hint(self):
        super()._update_prompt_hint()
        if getattr(self, "_easy", False):
            self.b_describe.pack_forget()

    def _set_inventory(self, inv, err: str = ""):
        super()._set_inventory(inv, err)
        self._easy_refresh()

    def _apply_settings(self, s: dict) -> list:
        notes = super()._apply_settings(s)
        self._easy_refresh()            # a loaded run or preset may name a function or model Easy Mode does not offer
        return notes

    # ---------- the Easy Mode tab of the settings window ----------

    def open_settings(self, focus=None):
        super().open_settings(focus)
        nb, frame = getattr(self, "nb_settings", None), getattr(self, "_easy_tab", None)
        try:
            if nb is None or (frame is not None and frame.winfo_exists()):
                return
            self._easy_tab = ttk.Frame(nb)
            nb.insert(0, self._easy_tab, text=em.TAB_TITLE)          # in front of "Models" and "Credits"
            self._easy_tab_draw()
        except tk.TclError:
            pass

    def _settings_fill(self):
        super()._settings_fill()
        self._easy_tab_draw()

    def _starter_missing(self) -> list:
        """The files of the starter models that are missing (required ones, listed once even when two models share them)."""
        if self.inv is None:
            return []
        out = []
        for row in self.inv.rows():
            if row["key"] in em.STARTER_MODELS:
                out += [f for f, found, lv in row["files"] if found is None and lv == "required" and f not in out]
        return out

    def _easy_tab_draw(self):
        """The tab: what Easy Mode needs, what is missing, and the button that gets the starter models."""
        frame = getattr(self, "_easy_tab", None)
        if frame is None:
            return
        try:
            if not frame.winfo_exists():
                return
            for w in frame.winfo_children():
                w.destroy()
        except tk.TclError:
            return
        box = ttk.Frame(frame)
        box.pack(fill="both", expand=True, padx=12, pady=10)

        def label(text, style="", pady=(0, 4), mark=None):
            lb = ttk.Label(box, text=text, style=SET_STYLES.get(style, "SetText.TLabel"), justify="left", wraplength=self._px(640))
            lb.pack(anchor="w", pady=pady)
            return lb

        label(em.TAB_INFO, pady=(0, 8))
        if self.inv is None:
            label("ComfyUI could not be read. Start ComfyUI, then click the refresh arrow (⟳) at the bottom of the plugin.", "bad")
            return
        missing = self._starter_missing()
        self._dl_widgets_easy = {}
        if missing:
            busy = any(f.name in self._dl for f in missing)
            total = size_text(sum(f.size for f in missing))
            b = ttk.Button(box, text=f"{em.TAB_BUTTON} ({total})", style="SetSmall.TButton",
                           command=lambda: self.download_missing(em.STARTER_MODELS, required_only=True))
            b.pack(anchor="w", pady=(0, 6))
            if busy:
                b.configure(state="disabled")
            Tooltip(b, "Downloads the missing files of the starter models. Files that need a website open their page in your browser.")
        else:
            label("All starter models are installed.", "ok", pady=(0, 6))
        for row in self.inv.rows():
            if row["key"] not in em.STARTER_MODELS:
                continue
            head = label(row["label"], "head", pady=(6, 2))
            head.configure(image=self.state_dot(row["status"].state), compound="left")
            if row["key"] == "flux3" and any(browser_only(f) for f in missing):
                label(em.TAB_FLUX3_NOTE, "note", pady=(0, 2))
            for f in (f for f in missing if any(f is x for x, _fd, _lv in row["files"])):
                self._easy_file_row(box, f)
        label(em.TAB_MORE, "muted", pady=(16, 0))

    def _easy_file_row(self, parent, f):
        """One missing file: its name and size, or (while it loads) a bar, the percent and a cross to stop it."""
        line = ttk.Frame(parent)
        line.pack(fill="x", anchor="w")
        st = self._dl_info(f.name)
        if st:
            cancel = ttk.Button(line, text="✕", style="Link.TButton", width=2, command=lambda n=f.name: self.download_cancel(n))
            cancel.pack(side="right", padx=(4, 0))
            Tooltip(cancel, "Stop this download. What is loaded stays, loading it again goes on where it stopped.")
            lb = ttk.Label(line, text="", style=SET_STYLES["muted"], width=8, anchor="e")
            lb.pack(side="right")
            bar = ttk.Progressbar(line, length=self._px(120), maximum=max(st["total"], 1), value=st["done"])
            bar.pack(side="right", padx=(8, 4))
            self._dl_widgets_easy[f.name] = {"bar": bar, "label": lb}
            self._dl_paint(f.name)
        else:
            ttk.Label(line, text=f.size_text, style=SET_STYLES["muted"], width=8, anchor="e").pack(side="right")
        text = f"      {f.name}"
        if f.name in self._dl_restart:
            text += "   (loaded: restart ComfyUI)"
        elif browser_only(f):
            text += "   (opens its page in your browser)"
        ttk.Label(line, text=text, style=SET_STYLES["muted"], justify="left", wraplength=self._px(480)).pack(side="left")

    # ---------- the switch ----------

    def toggle_easy(self):
        on = bool(self.v_easy.get())
        if on == bool(getattr(self, "_easy", False)):
            return
        if self.worker and self.worker.is_alive():
            self.v_easy.set(not on)
            self._status("Wait until the run is finished.")
            return
        if on:
            self._easy_enter()
        else:
            self._easy_leave()

    def _easy_enter(self):
        snap = self._collect()
        snap["model"] = self.v_model.get()
        em.save_return(snap)            # the normal mode comes back exactly like this
        self._easy = True
        em.set_on(True)
        self.v_seed.set(-1)             # always a new random seed
        self._easy_busy = True
        try:
            picks = self._easy_models()
            mode = self.v_mode.get()
            if not picks.get(mode):
                mode = next((m for m in em.EASY_MODES if picks[m]), mode)
                self.v_mode.set(mode)
            key = picks.get(mode, "")
            if key:
                self.v_model.set(key)
                self._on_model()        # the model's factory settings (no saved page in Easy Mode)
        finally:
            self._easy_busy = False
        self._update_mode_radios()
        self._apply_start_state()
        self._easy_hide()
        self._fit_height()
        self._status(em.STATUS_ON)

    def _easy_leave(self):
        snap = em.pop_return()
        self._easy = False
        em.set_on(False)
        self._easy_show()
        key = snap.pop("model", "")
        snap.pop("prompt", None)        # one prompt box for both modes: the text stays
        if key:
            self.v_model.set(key)
            self._last_model = key
        if snap:
            self._apply_settings(snap)
        self._update_mode_radios()
        self._apply_start_state()
        self._on_mode_ui()
        self._on_workflow()
        self._fit_height()
