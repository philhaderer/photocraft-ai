"""Easy Mode in the window (PLAN.md point 17): the switch in the header, hiding what Easy Mode does not show, the model the
plugin picks for each function. The logic without Tk is in easymode.py. Switched off, the window behaves as before."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from . import easymode as em
from .ui_settings import FOOT_RESET_PADX


class EasyMixin:
    # ---------- building ----------

    def _build_easy(self):
        """The switch (left of the clock) and the model line under the function buttons. Called at the end of _build."""
        self.b_easy = ttk.Checkbutton(self.f_header, text=em.SWITCH_TEXT, variable=self.v_easy, command=self.toggle_easy,
                                      style="Small.Toolbutton", image=self._icon("toggle"), compound="left")
        self.b_easy.pack(side="right", padx=(0, 8))
        Tooltip(self.b_easy, em.SWITCH_TIP)
        self.v_easy_model = tk.StringVar(value="")
        self.lbl_easy_model = ttk.Label(self.f_tabs, textvariable=self.v_easy_model, style="Muted.TLabel")

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
        mode = self.v_mode.get()
        picks = self._easy_models()
        key = picks.get(mode) or self.v_model.get()
        line = em.model_line(key) if key else ""
        self.v_easy_model.set(line or em.NO_MODELS)
        if not self.lbl_easy_model.winfo_manager():
            self.lbl_easy_model.pack(fill="x", pady=(6, 0), anchor="w")

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
        self._status(em.STATUS_OFF)
