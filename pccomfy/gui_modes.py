"""Model tabs, modes, workflow choice, stages and the controls that depend on them. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from .workflows import lora_subgraph as workflows_lora_subgraph, stage_subgraph as workflows_stage_subgraph


class ModeMixin:
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
        if mode == "upscale":
            self.f_scale.pack(fill="x", padx=10, pady=4, after=self._below_prompt())   # under the LLM row, above the LoRA
        else:
            self.f_scale.pack_forget()
        if mode in SCALE_MODES:              # also Fibo Refine, which runs as Edit (user 28.10.)
            self._pack_post(self.f_detail)
        else:
            self.f_detail.pack_forget()
        self.w_denoise.configure(state="disabled" if mode == "txt2img" or self._ignores_mask() else "normal")   # an editor always runs at 1.0
        expand = mode == "outpaint"        # Expand image: the plugin's own defaults, none of the finishing options
        if self._run_mode() in ("txt2img", "edit") + SCALE_MODES or expand:    # nothing to blend into / a new document / the whole picture: no layer mask
            self.f_lm.pack_forget()
        else:
            self._pack_post(self.f_lm)                 # the last row of the finishing options
        for w in self._match_widgets:      # pulling colours back only makes sense where a new area meets the old picture
            if mode == "inpaint":
                w.grid()
            else:
                w.grid_remove()
        for w in self._sharp_widgets:
            if expand:
                w.grid_remove()
            else:
                w.grid()
        if expand:        # the frame would keep its height with nothing in it: a gap above Context (live finding 28.10.)
            self.f_sharp.pack_forget()
        else:
            self._pack_post(self.f_sharp)
        self._show_enhance_box(self._llm_row_wanted())
        self._update_prompt_hint()
        self._sync_prompt_field(mode)
        self._update_feather_state()
        self._update_availability()
        if self._sized:
            self._fit_height()

    def _run_mode(self) -> str:
        """The mode the bridge runs: the selected one, unless the model's mode says otherwise (Fibo Refine runs as Edit)."""
        mode = self.v_mode.get()
        m = self._model()
        spec = m.modes.get(mode) if m else None
        return (spec.run_as if spec and spec.run_as else mode)

    def _scale(self) -> float:
        try:
            return min(8.0, max(1.0, float(str(self.v_scale.get()).strip().lstrip("xX×").strip().replace(",", "."))))
        except ValueError:
            return 2.0

    def _model(self):
        return models.BY_KEY.get(self.v_model.get())

    def _seam_mode(self) -> str:
        """The seam correction for the chosen model: "on" or "off" (a workflow of your own: off)."""
        m = self._model()
        return m.seam if m else "off"

    def _custom_workflow(self) -> bool:
        """A workflow of your own is chosen (no model): every function is offered as it is."""
        return not self.v_model.get() and self.v_workflow.get() not in ("", BUILTIN)

    def _update_mode_radios(self):
        """The functions are always there (two per row); "Image -> image" only for a workflow of your own. Below them, a
        model that cannot do the chosen function is greyed out in its place (_update_model_chips)."""
        m = self._model()
        shown = []
        hidden = cfgmod.hidden_tabs()
        for key, _label in MODE_LABELS:
            rb = self.rb_modes[key]
            if key == "img2img" and not self._custom_workflow():
                rb.grid_remove()           # no model uses it
                continue
            # greyed out when every model that can do it is hidden (right-click menu, gear window)
            offered = self._custom_workflow() or any(key in x.modes and x.key not in hidden for x in models.MODELS)
            rb.configure(state="normal" if offered else "disabled")
            self.tt_modes[key].text = models.function_tip(key, MODE_TIPS[key])
            shown.append(key)
        for i, key in enumerate(shown):
            self.rb_modes[key].grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        self._update_model_chips()

    def _update_model_chips(self):
        """A hidden model (right-click menu, gear window) leaves the row; the others close up, three per row."""
        mode = self.v_mode.get()
        hidden = cfgmod.hidden_tabs()
        i = 0
        for m in models.MODELS:
            rb = self.rb_tabs.get(m.key)
            if rb is None:
                continue
            if m.key in hidden:
                rb.grid_remove()
                continue
            rb.grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=2)
            i += 1
            rb.configure(state="normal" if (mode in m.modes or self._custom_workflow()) else "disabled")

    def _chip_menu(self, key: str, event):
        """Right-click on a model chip (L3, user 29.10.): this model as the favourite of the chosen function (a tick in the
        menu, no mark on the chip), or hide the model (it comes back in the gear window, tab "Models")."""
        m = models.BY_KEY.get(key)
        if m is None:
            return
        mode = self.v_mode.get()
        menu = self.m_chip
        menu.delete(0, "end")
        self.v_chip_fav.set(cfgmod.favorites().get(mode) == key)
        here = self.v_model.get() == key and mode in m.modes          # saving takes the window as it is: only for the chosen model
        menu.add_command(label="Set as my settings for this mode and model", state="normal" if here else "disabled",
                         command=lambda: self._save_page(key))
        menu.add_separator()
        menu.add_checkbutton(label=f"Favourite for {dict(MODE_LABELS).get(mode, mode)}", variable=self.v_chip_fav,
                             state="normal" if mode in m.modes else "disabled",
                             command=lambda: cfgmod.set_favorite(mode, key if self.v_chip_fav.get() else None))
        menu.add_command(label="Hide this model", command=lambda: self._set_model_hidden(key, True))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _save_page(self, key: str):
        """The window's settings (not the prompt, the seed or the page itself) become the starting settings of this model and
        function: every time the page opens, and with "Reset page", they come back (user 30.10., renamed 31.10.)."""
        mode = self.v_mode.get()
        try:
            s = {k: v for k, v in self._collect().items() if k not in PAGE_NOT_SAVED}
        except (tk.TclError, ValueError, TypeError) as e:
            self._status(f"Could not save the settings: {e}", error=True)
            return
        cfgmod.set_saved_page(key, mode, s)
        self._status(f"Saved my settings for {dict(MODE_LABELS).get(mode, mode)} with {models.BY_KEY[key].label}.")

    def _set_model_hidden(self, key: str, hidden: bool):
        """Hide or show a model chip. Hiding the chosen model chooses another one for the function (_model_for_mode), else
        the first model still shown; with every model hidden, none is chosen."""
        cfgmod.set_tab_hidden(key, hidden)
        if hidden and self.v_model.get() == key:
            shown = [m.key for m in models.MODELS if m.key not in cfgmod.hidden_tabs()]
            new = self._model_for_mode(self.v_mode.get()) or (shown[0] if shown else "")
            self.v_model.set(new)
            if new:
                self._on_model()
            else:
                self.v_workflow.set(BUILTIN)
                if hasattr(self, "_apply_start_state"):
                    self._apply_start_state()
        self._update_mode_radios()
        self._fit_height()

    def _model_for_mode(self, mode: str) -> str:
        """The model a function opens with when the chosen one cannot do it: the favourite of the function (right-click
        menu), else the one last used for it, else the first in the fixed order (Easy Mode will choose the best one later).
        Hidden models are left out; a model whose files are missing comes last."""
        hidden = cfgmod.hidden_tabs()
        usable = [m.key for m in models.MODELS if mode in m.modes and m.key not in hidden]
        if not usable:
            return ""
        last = self.__dict__.setdefault("_mode_model", dict(self.state.get("model_by_mode") or {})).get(mode)
        fav = cfgmod.favorites().get(mode)
        ok = getattr(self, "_model_usable", lambda key, mode: True)
        for key in [k for k in (fav, last) if k in usable] + usable:
            if ok(key, mode):
                return key
        return usable[0]

    def _remember_model_for_mode(self):
        key, mode = self.v_model.get(), self.v_mode.get()
        if key and not getattr(self, "_booting", False):
            mm = self.__dict__.setdefault("_mode_model", dict(self.state.get("model_by_mode") or {}))
            mm[mode] = key

    def _on_model(self):
        """A model was clicked: keep the function when the model has it, else its first one; start with the model's settings."""
        m = self._model()
        if m is None:
            return
        self._remember_model_for_mode()
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
        # the colour pull-back and the sharpening belong to the model's mode, they do not travel to the next tab
        # (sharpen: user 28.10., a function without its own value starts at 0 %)
        s = {"match": 0.0, "sharpen": 0.0, **spec.settings}
        # a mode without a Context of its own starts at the function's default, not at what the tab before had
        # (Fibo Fill showed 0.4 after Qwen and 0.2 after Reset)
        s.setdefault("context", FILL_CONTEXT if mode == "inpaint" else self._ctx_default)
        s.setdefault("mask_density", 100)      # likewise: a density set by hand does not travel to the next function
        if not keep:
            s["workflow"] = spec.workflow
        elif not force:
            s.pop("enhance", None)       # same workflow: the "LLM prompt enhancement" checkbox keeps what you set (Expand ignores it)
        if getattr(self, "_easy", False):
            s["enhance"] = False       # Easy Mode: always the factory settings, no saved page, no LLM (its row is hidden)
        elif not getattr(self, "_factory", False):         # Shift + "Reset page": the standard settings, not the saved ones
            s.update(cfgmod.saved_page(m.key, mode))      # settings the user saved for this page (chip menu) replace the starting ones
        self._switch_context(mode)   # first: the context memory belongs to the mode, the defaults below overwrite its value
        self._apply_settings(s)
        t = self.t_prompt
        cur = t.get("1.0", "end").strip() if str(t.cget("state")) != "disabled" else ""
        first = spec.prompts[0] if spec.prompts else None      # Flux 2 Refine: always starts on its "Default" prompt
        if first is not None and str(t.cget("state")) != "disabled":
            t.edit_separator()                  # one undo step: Ctrl+Z in the field brings your own text back
            t.delete("1.0", "end")
            t.insert("1.0", first[1])
            t.edit_separator()
            self.v_pchoice.set(first[0])
        elif (cur == "" or cur in models.STOCK_PROMPTS) and str(t.cget("state")) != "disabled":   # an unedited stock text is replaced
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

    def _show_advanced(self):
        opened = bool(self.v_adv_open.get())
        self.btn_adv.configure(text="Advanced settings", compound="left",
                               image=self._icon("chevron-down" if opened else "chevron-right", MUTED))
        if opened:
            self.adv_body.pack(fill="x", pady=(4, 0))
        else:
            self.adv_body.pack_forget()

    def _toggle_advanced(self):
        self.v_adv_open.set(not self.v_adv_open.get())
        self._show_advanced()
        self._fit_height()

    def _reset_detail(self):
        """"Mix source image/new image" starts at 100 % (only the new image) whenever a function or tab is chosen."""
        if not getattr(self, "_booting", False):
            self.v_detail.set(1.0)
            self._on_detail()

    def _on_mode(self):
        """A function was clicked. When the chosen model cannot do it (or none is chosen yet), the function picks its model
        (_model_for_mode) and opens with that model's settings; otherwise the model stays."""
        m = self._model()
        mode = self.v_mode.get()
        if not getattr(self, "_booting", False) and not self._custom_workflow() and (m is None or mode not in m.modes):
            key = self._model_for_mode(mode)
            if key:
                self.v_model.set(key)
                self._on_model()
                return
        self._remember_model_for_mode()
        self._reset_detail()
        if self.v_model.get():
            self._apply_model_mode()
        else:
            self._couple_workflow()
        self._on_mode_ui()
        self._on_workflow()
        self._mode_denoise()

    def _mode_denoise(self):
        """The Denoise a function starts with (after the workflow's own value was read)."""
        mode = self.v_mode.get()
        if mode in ("inpaint", "remove", "outpaint", "edit", "multi_edit", "txt2img"):
            self.v_denoise.set(1.0)  # full denoise inside the mask; lower it to keep more of the original (text to image: always 1.0)
        elif mode == "img2img" and self.v_denoise.get() >= 0.99 and not self._ignores_mask():
            self.v_denoise.set(0.6)   # not for Fibo-type editors: below 1.0 they produce a different, broken picture

    def _reset_click(self, event=None):
        """The footer button: a click resets to the saved settings of the page (else the standard ones); Shift + click always
        to the standard ones (the way back after "Set as my settings"; PLAN.md, user 31.10. option B)."""
        self.reset_settings(factory=bool(getattr(self, "_shift_down", False)))

    def reset_settings(self, factory: bool = False):
        """Everything in the window back to what a fresh start has: this tab and function stay, their starting settings come back,
        the prompt, the negative prompt, extra LoRAs, seed and the finishing sliders are cleared. Also while a run is on
        (user 30.10.): the run took its own copy of the settings at Generate, Generate stays grey until it is done."""
        self._factory = factory
        try:
            self._reset_settings()
        finally:
            self._factory = False
        if factory:
            self._status("Reset to the standard settings (your saved ones are ignored).")

    def _reset_settings(self):
        d = self.cfg["defaults"]
        self.v_seed.set(-1)
        self.v_variants.set(int(d["variants"]))
        self.v_grow.set(int(d["mask_grow"]))
        self.v_blur.set(int(d["mask_blur"]))
        self.v_overlap.set(int(d["overlap"]))
        self.v_res.set(int(d["base_res"]))
        self.v_denoise.set(1.0)       # as a new window has it; the workflow's own value and the function's rule follow below
        self.v_sharpen.set(0.0)
        self.v_match.set(0.0)
        self.v_feather.set(2.0)
        self.v_density.set(100)
        self.v_live.set(True)
        self.v_detail.set(1.0)
        self.v_lmask.set(LAYER_MASKS["soft"])       # the model's function sets its own below
        self.v_cmp_res.set("")
        self.v_cmp_ctx.set("")
        self.v_scale.set(scale_text(1.5))
        self.t_neg.delete("1.0", "end")
        if str(self.t_prompt.cget("state")) != "disabled":
            self.t_prompt.delete("1.0", "end")
        self._prompt_kept = ""
        self._set_loras([])
        # what the tab's settings may leave as they were: back to a fresh start too (the panels you opened stay open)
        self.v_enhance.set(False)          # off like every start value (user 30.10.)
        self.v_turbo.set(True)
        if getattr(self, "v_bbox", None) is not None:      # BBOX (Flux 3 Multi Image Edit), made with the reference slots
            self.v_bbox.set(False)
            self._refs_bbox_changed()
        self.v_clip.set(CLIP_DEFAULT)
        self.v_pchoice.set("")
        self.v_lora_str.set(1.0)
        self._lora_wf = None                     # the LoRA slider starts at the value the workflow ships with (else 1.0)
        self._ctx.pop(self.v_mode.get(), None)      # only this function forgets its Context value; the others keep theirs
        self._ctx.setdefault("inpaint", FILL_CONTEXT)
        self.v_context.set(self._ctx.get(self.v_mode.get(), d["context"]))
        self._ctx_mode = self.v_mode.get()
        self._vals_key = None                    # steps / CFG / sampler / scheduler are read from the workflow again
        if self.v_model.get():
            self._apply_model_mode(force=True)
        self._on_mode_ui()
        self._on_workflow()
        self._mode_denoise()
        self._on_sharpen()
        self._on_match()
        self._on_feather()
        self._on_density()
        self._fit_height()
        self._status("Reset to the startup settings.")

    def _pack_post(self, frame):
        """Show one of the finishing rows in its place: Mix source/new, Sharpen and Match colours, Context, Edge feather, Layer mask."""
        shown = (lambda f: bool(f.winfo_manager())) if hasattr(frame, "winfo_manager") else (lambda f: False)
        if shown(frame):
            return
        order = [f for f in (getattr(self, n, None) for n in ("f_detail", "f_sharp", "f_ctx", "f_feather", "f_density", "f_lm")) if f is not None]
        later = [f for f in order[order.index(frame) + 1:] if shown(f)] if frame in order else []
        frame.pack(fill="x", pady=(2, 0), **({"before": later[0]} if later else {}))

    def _uses_soft_mask(self) -> bool:
        """True when the new layer really gets the soft (feathered) layer mask, i.e. the feather has an effect."""
        choice = layer_mask_key(self.v_lmask.get())
        if self.v_mode.get() == "txt2img":
            return False
        return choice == "soft"

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
            self._pack_post(self.f_feather)
        elif not on and shown:
            self.f_feather.pack_forget()
        fd = getattr(self, "f_density", None)    # Mask density goes with it
        if fd is not None:
            self.w_density.configure(state="normal" if on else "disabled")
            if hasattr(fd, "winfo_manager"):
                if on and not fd.winfo_manager():
                    self._pack_post(fd)
                elif not on and fd.winfo_manager():
                    fd.pack_forget()
        b = getattr(self, "b_fprev", None)
        if b is not None and hasattr(b, "winfo_manager"):
            if on and not b.winfo_manager():
                b.pack(side="left")
            elif not on and b.winfo_manager():
                b.pack_forget()
        if getattr(self, "_fprev_on", False):    # the feather preview follows: new settings shown, or ended with the slider
            if on:
                self._refresh_feather_preview()
            else:
                self.toggle_feather_preview(show=False)
        if on != shown and getattr(self, "_sized", False):
            self._fit_height()

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

    def _switch_missing(self) -> dict:
        """What the window's switches need that ComfyUI does not have: {"turbo" or "stage<i>": (label, [file or node names])}.
        A switch needs the loaders of its LoRA / stage nodes (and the node classes of a stage). Nothing is checked while the
        inventory was not read or the workflow is not one of ours."""
        out: dict = {}
        if getattr(self, "inv", None) is None:
            return out

        def names(sub):
            files, classes = self.inv.check_workflow(sub)
            return [n for _k, n in files] + list(classes)

        for t in self._wf_templates():
            sub = workflows_lora_subgraph(t)
            if sub and names(sub):
                out["turbo"] = (self._lora_label(), names(sub))
            for i, st in enumerate(stage_info(t)[:3]):
                miss = names(workflows_stage_subgraph(t, st["id"]))
                if miss:
                    out[f"stage{i}"] = (st["label"], miss)
            break
        return out

    def _enforce_switch_files(self) -> list[str]:
        """A switch whose files are missing is greyed out with the file in its tooltip and cannot be on: the mode itself keeps
        working with the standard settings. A switch that a loaded setting (history, preset, saved page) wanted on is switched
        off and named in the returned notes, so the user sees why (user 30.10.)."""
        if not hasattr(self, "stage_cbs"):
            return []
        miss = self._switch_missing()
        notes: list[str] = []
        rows = [("turbo", self.cb_turbo, self.v_turbo, self.tt_turbo, self._has_lora_switch())]
        stages = self._stages()
        rows += [(f"stage{i}", cb, self.stage_vars[i], self.stage_tips[i], i < len(stages)) for i, cb in enumerate(self.stage_cbs)]
        for key, cb, var, tip, exists in rows:
            if not exists:
                continue
            if key in miss:
                label, names = miss[key]
                cb.configure(state="disabled")
                tip.text = (tip.text + "\n\n" if tip.text else "") + f"Needs {', '.join(names[:3])}: download it in the settings (gear)."
                if var.get():
                    var.set(False)
                    notes.append(f"{label} needs {', '.join(names[:2])}")
            else:
                cb.configure(state="normal")
        if notes:
            self._on_turbo()
            self._update_stage_scales()
        return notes

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
                if st is not None:
                    self.stage_cbs[i].grid_configure(columnspan=2)     # no slider: its text may use the slider's room
                continue
            self.stage_cbs[i].grid_configure(columnspan=1)
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

    def _on_context(self, _value=None):
        """The Context slider moved: it goes in steps of 0.05."""
        try:
            v = float(self.v_context.get())
        except (tk.TclError, ValueError):
            return
        snapped = min(1.0, max(0.0, round(v * 20) / 20))
        if abs(snapped - v) > 1e-9:
            self.v_context.set(snapped)
        self._show_context()

    def _show_context(self):
        box = getattr(self, "lbl_context", None)
        if box is not None:
            try:
                box.configure(text=f"{round(float(self.v_context.get()) * 100)} %")
            except (tk.TclError, ValueError):
                pass

    def _on_density(self, _value=None):
        v = int(round(float(self.v_density.get())))
        if v != self.v_density.get():
            self.v_density.set(v)
        self.lbl_density.configure(text=f"{v} %")

    def _on_feather(self, _value=None):
        v = round(float(self.v_feather.get()) * 2) / 2
        self.lbl_feather.configure(text="hard edge" if v <= 0 else f"{v:g} %")
        self._refresh_feather_preview()

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
        masked = mode in ("inpaint", "remove", "outpaint")
        editor = self._ignores_mask()

        def on(widget, yes, normal="normal"):
            widget.configure(state=normal if yes else "disabled")

        on(self.w_denoise, not (mode == "txt2img" or editor or scale))
        # the upscale workflow gives one picture; grey while a run is on (part of Generate, also after Defaults or a tab change)
        on(self.w_variants, not scale and not getattr(self, "_running", False))
        on(self.w_adv["Base res."], not scale)               # the picture goes in at its own size
        t2i = mode == "txt2img"            # Context, Mask grow and Mask blur mean nothing without a picture: not shown
        for k in ("Context", "Mask grow", "Mask blur"):
            for w in (self.l_adv[k], self.w_adv[k]):
                if t2i:
                    w.grid_remove()
                else:
                    w.grid()
        on(self.w_adv["Context"], masked)
        if masked:                         # Context (under Edge feather) only where there is a selection around which to look
            self._pack_post(self.f_ctx)
        elif hasattr(self.f_ctx, "pack_forget"):
            self.f_ctx.pack_forget()
        on(self.w_adv["Mask grow"], masked and not editor)
        on(self.w_adv["Mask blur"], masked and not editor)
        on(self.cb_lm, mode != "upscale", "readonly")        # Upscale opens a new document: no layer to mask
        on(self.t_neg, self._wf_has_tag("negative"))
        self.t_neg.configure(fg=FG if self._wf_has_tag("negative") else DISABLED)

    def _on_workflow(self):
        # a custom workflow carries its own model/steps/CFG/sampler – these fields apply to the built-in one only
        state = "normal" if self.v_workflow.get() == BUILTIN else "disabled"
        self._sync_sampler_fields()
        # the text model applies to custom workflows (nodes tagged pc:clip), not to the built-in graph, and only
        # while the prompt enhancement is on
        # no text model here, or a fixed / ready-made prompt: the row is hidden, never a greyed-out box (user 30.10.)
        has_writer = self._llm_row_wanted()
        self._show_enhance_box(has_writer)
        llm = next((m for m in (writer_model(t) for t in self._wf_templates()) if m), "")
        name = next((n for n in (writer_name(t) for t in self._wf_templates()) if n), "")
        # the model's name only in the tooltip, never in the checkbox (user 30.10.)
        self.tt_enhance.text = ENHANCE_TIP + (f"\nText model: {name}" if name else "") + (f"\n{llm}" if " " in llm and llm != name else "")
        self.cb_enhance.configure(text="LLM prompt enhancement")
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
        m = self._model()
        spec = m.modes.get(self.v_mode.get()) if m else None
        self.tt_steps.text = spec.steps_tip if spec else ""
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
        self._enforce_switch_files()
        self._update_options_box(has_lora, stages)
        self.w_detail.configure(state="normal" if self._run_mode() in SCALE_MODES else "disabled")
        enhancing = has_writer and bool(self.v_enhance.get())
        self.cb_clip.configure(state="readonly" if (state == "disabled" and enhancing) else "disabled")
        self._update_feather_state()
        self._update_availability()

    def _on_turbo(self):
        """The workflow's own LoRA (DMD2, Turbo ...) switched on or off: Steps and CFG take the workflow's values for that
        case (pc_no_lora: e.g. 25 steps instead of 8), and its strength slider follows the checkbox."""
        self._sync_sampler_fields()
        self.w_lora_str.configure(state="normal" if self._has_lora_switch() and self.v_turbo.get() else "disabled")

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
        # Sampler and Scheduler can be changed (under Advanced); Flux 2 Klein's own scheduler is "Flux2Scheduler" in the list
        names = [n for n in getattr(self, "_sched_names", []) if n != FLUX2_SCHEDULER]
        self.cb_sched["values"] = ([FLUX2_SCHEDULER] + names) if vals.get("scheduler") == FLUX2_SCHEDULER else names
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

    def _llm_row_wanted(self) -> bool:
        """The "LLM prompt enhancement" row is shown only where the workflow has a text model that writes the prompt and the
        function takes the user's own prompt (not in NO_LLM_MODES)."""
        return self.v_mode.get() not in NO_LLM_MODES and self._has_text_model()

    def _has_text_model(self) -> bool:
        """True when the selected workflow (or one of a group) contains a text model that writes the prompt."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return False
        try:
            return any(prompt_phase_nodes(load_template(w)) for w in resolve(self.workflows_dir / wf))
        except (OSError, ValueError, KeyError):
            return False
