"""Settings state: collect, apply, refresh from PhotoCraft, saved state. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
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
        self.templates = [t for t in list_templates(self.workflows_dir) if t.name not in models.PARKED_WORKFLOWS]
        self.cb_workflow["values"] = [BUILTIN] + [t.name for t in self.templates]
        if self.v_workflow.get() not in self.cb_workflow["values"]:
            # gone (or parked): the chosen model's own workflow for this function, so the model stays
            m = self._model()
            spec = m.modes.get(self.v_mode.get()) if m else None
            self.v_workflow.set(spec.workflow if spec and spec.workflow in self.cb_workflow["values"] else BUILTIN)
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

    # ---------- collect / apply (history, saved pages) ----------

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
            "enhance": bool(self.v_enhance.get()),
            "turbo": bool(self.v_turbo.get()), "stage_on": bool(self.v_stage.get()), "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "loras": self._loras(), "sharpen": round(float(self.v_sharpen.get()), 2), "match": round(float(self.v_match.get()), 2), "detail": round(float(self.v_detail.get()), 2),
            "lora_strength": round(float(self.v_lora_str.get()), 2),
            "layer_mask": layer_mask_key(self.v_lmask.get()),
            "feather_pct": round(float(self.v_feather.get()), 1),
            "mask_density": int(self.v_density.get()),
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
        put(self.v_density, "mask_density", int)
        self._on_density()
        if "layer_mask" in s:
            self.v_lmask.set(LAYER_MASKS[layer_mask_key(s["layer_mask"])])
        self._update_feather_state()
        notes += self._enforce_switch_files()
        for widget, key in ((self.t_prompt, "prompt"), (self.t_neg, "negative")):
            # an empty prompt in a preset means "not part of the preset": never wipe what was typed
            if str(s.get(key, "")).strip():
                widget.delete("1.0", "end")
                widget.insert("1.0", str(s[key]))
        self._on_mode_ui()
        self._on_workflow()
        self._sync_model()
        return notes

    def _save_state(self, req: Request):
        p = req.params
        cfgmod.save_state({
            "mode": self.v_mode.get(), "workflow": self.v_workflow.get(), "clip": p.clip, "checkpoint": p.checkpoint, "prompt": p.prompt,
            "negative": p.negative, "steps": p.steps, "cfg": p.cfg, "denoise": self.v_denoise.get(),
            "sampler": p.sampler, "scheduler": p.scheduler, "variants": req.variants, "base_res": req.base_res,
            "context": req.context, "mask_grow": req.mask_grow, "mask_blur": req.mask_blur, "overlap": req.overlap, "scale": req.scale,
            "on_top": bool(self.v_top.get()), "adv_open": bool(self.v_adv_open.get()), "model": self.v_model.get(), "neg_open": bool(self.v_neg_open.get()), "prompt_h": self._prompt_lines(), "enhance": bool(self.v_enhance.get()), "turbo": req.turbo, "layer_mask": req.layer_mask, "mask_density": req.mask_density,
            "stage_on": req.stage_on, "stage2_on": bool(self.v_stage2.get()), "stage3_on": bool(self.v_stage3.get()), "stage_strengths": [round(float(v.get()), 2) for v in self.v_sstr], "detail": req.detail, "sharpen": round(float(self.v_sharpen.get()), 2), "match": req.match, "loras": [list(x) for x in req.loras], "lora_strength": req.lora_strength if req.lora_strength is not None else self.state.get("lora_strength", 1.0),
            "runs": dict(self.state.get("runs", {})),
            "model_by_mode": dict(getattr(self, "_mode_model", None) or self.state.get("model_by_mode") or {}),
            "win_pos": list(getattr(self, "_win_pos", None) or self.state.get("win_pos") or []) or None,
        })
