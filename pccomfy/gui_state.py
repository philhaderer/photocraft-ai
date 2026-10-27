"""Settings state: collect, apply, presets, refresh from PhotoCraft, saved state. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401


class StateMixin:
    # ---------- connections ----------

    def refresh(self):
        def work():
            info = {}
            try:
                self.pc.close()
                self.pc.ping()
            except PhotoCraftError as e:
                info["err"] = str(e)         # shown as a message; the footer has no PhotoCraft mark
            try:
                info["ckpts"] = self.comfy.checkpoints()
                info["samplers"] = self.comfy.samplers()
                info["clips"] = self.comfy.clips()
                info["loras"] = self.comfy.loras()
                info["scheds"] = self.comfy.schedulers()
                info["fooocus"] = self.comfy.fooocus_inpaint()
                info["comfy"] = True
            except ComfyError as e:
                info["comfy"] = False
                info.setdefault("err", str(e))
            self.events.put(("refresh", info))
        threading.Thread(target=work, daemon=True).start()

    def _apply_refresh(self, info):
        self.v_conn.set("ComfyUI connected" if info.get("comfy") else "ComfyUI not connected")
        set_dot(self.lbl_dot, bool(info.get("comfy")))
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
            self._sched_names = list(info["scheds"])
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
            "scale": self._scale(),
            "fooocus": bool(self.v_fooocus.get()), "enhance": bool(self.v_enhance.get()),
            "turbo": bool(self.v_turbo.get()), "stage_on": bool(self.v_stage.get()), "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "loras": self._loras(), "sharpen": round(float(self.v_sharpen.get()), 2), "match": round(float(self.v_match.get()), 2), "detail": round(float(self.v_detail.get()), 2),
            "lora_strength": round(float(self.v_lora_str.get()), 2),
            "layer_mask": layer_mask_key(self.v_lmask.get()),
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
        if self.v_mode.get() not in dict(MODE_LABELS):      # a mode that no longer exists (the old "reference"): the first one
            self.v_mode.set(MODE_LABELS[0][0])
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
        put(self.v_sharpen, "sharpen", float)
        put(self.v_match, "match", float)
        self._on_sharpen()
        self._on_match()
        if "lora_strength" in s:
            self._lora_wf = self.v_workflow.get()
            put(self.v_lora_str, "lora_strength", float)
            self._on_lora_str()
        self._on_detail()
        put(self.v_feather, "feather_pct", float)
        self._on_feather()
        if "layer_mask" in s:
            self.v_lmask.set(LAYER_MASKS[layer_mask_key(s["layer_mask"])])
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
        settings = data.get("settings", data) if isinstance(data, dict) else {}
        blocked = self.preset_blocked(settings)      # L1: a preset whose model has missing files keeps the current tab and says why
        if blocked:
            settings = {k: v for k, v in settings.items() if k not in ("mode", "workflow", "model")}
        notes = ([blocked] if blocked else []) + self._apply_settings(settings)
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

    def _save_state(self, req: Request):
        p = req.params
        cfgmod.save_state({
            "mode": self.v_mode.get(), "workflow": self.v_workflow.get(), "clip": p.clip, "checkpoint": p.checkpoint, "prompt": p.prompt,
            "negative": p.negative, "steps": p.steps, "cfg": p.cfg, "denoise": self.v_denoise.get(),
            "sampler": p.sampler, "scheduler": p.scheduler, "variants": req.variants, "base_res": req.base_res,
            "context": req.context, "mask_grow": req.mask_grow, "mask_blur": req.mask_blur, "overlap": req.overlap, "scale": req.scale,
            "preset": self.v_preset.get(), "on_top": bool(self.v_top.get()), "adv_open": bool(self.v_adv_open.get()), "model": self.v_model.get(), "neg_open": bool(self.v_neg_open.get()), "prompt_h": self._prompt_lines(), "fooocus": req.fooocus, "enhance": bool(self.v_enhance.get()), "turbo": req.turbo, "layer_mask": req.layer_mask,
            "stage_on": req.stage_on, "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "detail": req.detail, "sharpen": round(float(self.v_sharpen.get()), 2), "match": req.match, "loras": [list(x) for x in req.loras], "lora_strength": req.lora_strength if req.lora_strength is not None else self.state.get("lora_strength", 1.0),
            "runs": dict(self.state.get("runs", {})),
            "model_by_mode": dict(getattr(self, "_mode_model", None) or self.state.get("model_by_mode") or {}),
            "win_pos": list(getattr(self, "_win_pos", None) or self.state.get("win_pos") or []) or None,
        })
