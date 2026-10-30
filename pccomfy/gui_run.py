"""A run: build the request, generate, undo/redo, stop, poll, progress and status line. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from . import icons
from . import history as runhistory


class RunMixin:
    def _status(self, msg: str, error: bool = False):
        """The status line. An error gets a red "!" badge and red text, it never opens a dialog."""
        self.v_status.set(msg)
        self.lbl_status.configure(style="Error.TLabel" if error else "TLabel")
        if error:
            self.lbl_err.pack(side="left", padx=(0, 8), before=self.lbl_status)
        else:
            self.lbl_err.pack_forget()

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
        return Request(mode=self._run_mode(), params=p, remove_target=target, workflow=wf_path, base_res=int(self.v_res.get()),
                       context=min(1.0, max(0.0, round(float(self.v_context.get()) * 20) / 20)),   # the slider's range and steps (an old saved 2.0 too) mask_grow=int(self.v_grow.get()),
                       mask_blur=int(self.v_blur.get()),
                       overlap=int(self.v_overlap.get()), variants=int(self.v_variants.get()),
                       fooocus=bool(self.v_fooocus.get()), enhance=bool(self.v_enhance.get()) and self.v_mode.get() not in NO_LLM_MODES,
                       turbo=bool(self.v_turbo.get()), scale=self._scale(),
                       lora_strength=(round(float(self.v_lora_str.get()), 2) if self._has_lora_switch() else None),
                       stage_on=bool(self.v_stage.get()) or not self._stage_label(), stages_off=self._stages_off(), stage_strengths=self._stage_strengths(), sampler_override=self._sampler_override(), doc_tag=self._doc_tag(), loras=[tuple(x) for x in self._loras()], sharpen=0.0 if self.v_mode.get() == "outpaint" else round(float(self.v_sharpen.get()), 2), match=round(float(self.v_match.get()), 2), detail=round(float(self.v_detail.get()), 2) if self.v_mode.get() in SCALE_MODES else 1.0,
                       layer_mask=layer_mask_key(self.v_lmask.get()),
                       feather_pct=round(float(self.v_feather.get()) * 2) / 2,
                       mask_density=min(100, max(0, int(self.v_density.get()))),
                       seam=bool(self.v_seam.get()) and self._seam_mode() == "switch" and self._run_mode() in ("inpaint", "remove", "outpaint"),
                       seam_fixed=self._seam_mode() == "on" and self._run_mode() in ("inpaint", "remove", "outpaint"),
                       preview=bool(self.v_live.get()))

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

    def _show_variants(self):
        """The orange piece on the right of Generate says how many pictures a run makes: "×3 ▾", at 1 only "▾"."""
        try:
            n = int(self.v_variants.get())
        except (TypeError, ValueError, tk.TclError):
            n = 1
        self.w_variants.configure(text=f"×{n} ▾" if n > 1 else "▾")

    def _variants_menu(self):
        """A click on the piece beside Generate: the choice 1 to 8, opening under it."""
        b = self.w_variants
        try:
            self.m_variants.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            try:
                self.m_variants.grab_release()
            except Exception:
                pass

    def generate(self):
        if self.worker and self.worker.is_alive():
            return
        if self._needs_description() and not self.t_prompt.get("1.0", "end").strip():
            # an empty prompt fills the margin with unrelated things (A/B test 29.10.): no run, say what to do
            m = self._model()
            self._status(f"{m.label if m else 'This model'} needs a description of the surroundings: "
                         "click Describe or type one.", error=True)
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
            req.group_name = f"{SHORT_MODES.get(self.v_mode.get(), self.v_mode.get())} {req.run_no}"   # "Fill Selection 3"
            self.state["runs"] = runs
        self._save_state(req)
        self._history_begin(req)
        if getattr(self, "_fprev_on", False):   # the run ends the feather preview first (Bridge._run): the button follows
            if getattr(self, "_fprev_after", None):
                self.root.after_cancel(self._fprev_after)
                self._fprev_after = None
            self._fprev_on, self._fprev_dirty = False, None
            self.b_fprev.configure(text="Show feather")
        self._running = True
        self.b_go.configure(state="disabled")
        self.w_variants.configure(state="disabled")     # part of Generate: grey with it while a run is on
        self.b_undo.configure(state="disabled")
        self.b_redo.configure(state="disabled")
        self.b_stop.configure(state="normal")
        self._reset_progress()

        def progress(f, msg, phase="", phase_fraction=-1.0, elapsed=0.0):
            self.events.put(("progress", (f, msg, phase, phase_fraction, elapsed)))
        self.bridge.on_preview = lambda im: self.events.put(("preview", im))

        runs = sweep_requests(req, parse_list(self.v_cmp_res.get(), int), parse_list(self.v_cmp_ctx.get(), float))
        if len(runs) > 1:
            if req.params.seed is None or req.params.seed < 0:
                req.params.seed = random.randint(0, 2**31 - 1)   # one seed for the whole series: only the value differs

        def work():
            try:
                total = 0
                t_start = time.monotonic()
                for k, rq in enumerate(runs):
                    if len(runs) > 1:
                        self.events.put(("progress", (0.0, f"Comparison {k + 1}/{len(runs)}: {rq.label}", "prepare", -1.0, 0.0)))
                    res = self.bridge.run(rq, progress)
                    total += len(res["layers"])
                self.events.put(("vgl", res.get("vgl", "")))
                seam = res.get("seam")     # the seam correction's A/B: the tone jump of #1 in levels, before → after
                seam_text = f" · seam {seam[0]:.0f} → {seam[1]:.0f}" if seam else ""
                self.events.put(("done", f"Done · seed {res['seed']} · created {total} layer{'s' if total != 1 else ''}{seam_text} · {duration_text(time.monotonic() - t_start)}"))
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

    # ---------- the last runs (the clock in the header, history.py) ----------

    def _history_begin(self, req):
        """Generate was clicked: keep every setting of the window for the history; written once the run is done."""
        try:
            settings = self._collect()
        except (tk.TclError, ValueError, TypeError):
            self._hist_run = None
            return
        m = self._model()
        title = req.group_name or SHORT_MODES.get(self.v_mode.get(), self.v_mode.get())
        self._hist_run = runhistory.entry(title, m.label if m else "", settings)

    def _history_end(self, ok: bool):
        """The run is over: a finished one goes in front of the last runs; a cancelled or failed one is left out."""
        e, self._hist_run = getattr(self, "_hist_run", None), None
        if ok and e:
            runhistory.add(cfgmod.HISTORY_FILE, e)

    def _history_menu(self):
        """A click on the clock: the last 20 runs, newest first, opening under the button."""
        menu = self.m_history
        menu.delete(0, "end")
        runs = runhistory.load(cfgmod.HISTORY_FILE)
        for e in runs:
            menu.add_command(label=runhistory.label(e), command=lambda e=e: self.load_history(e))
        if not runs:
            menu.add_command(label="No runs yet.", state="disabled")
        b = self.b_history
        try:
            menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def load_history(self, e: dict):
        """A run from the clock's menu back into the window: every setting, a new seed, the text model's prompt with Enhance
        off when there was one (user 30.10.). Nothing starts; Ctrl+Z in the prompt field brings the old text back."""
        s = runhistory.settings_to_load(e)
        prompt, negative = str(s.pop("prompt", "")), str(s.pop("negative", ""))
        notes = self._apply_settings(s)
        if str(self.t_prompt.cget("state")) == "disabled":      # Remove object: the field is empty, the text is kept aside
            self._prompt_kept = prompt
        else:
            self.t_prompt.edit_separator()
            self.t_prompt.delete("1.0", "end")
            self.t_prompt.insert("1.0", prompt)
            self.t_prompt.edit_separator()
        self.t_neg.delete("1.0", "end")
        self.t_neg.insert("1.0", negative)
        name = e.get("title") or "the run"
        if notes:
            self._status(f"Loaded “{name}”, but: {', '.join(notes)}.", error=True)
        else:
            self._status(f"Loaded “{name}” with a new seed. Click Generate to run it.")

    # ---------- feather preview ----------

    def toggle_feather_preview(self, show: bool | None = None):
        """Show feather / Hide feather: the bridge shows the soft edge as Quick Mask in PhotoCraft and brings the user's
        selection back afterwards. Runs in the worker like undo (PhotoCraft is busy for a moment)."""
        show = (not getattr(self, "_fprev_on", False)) if show is None else show
        if self.worker and self.worker.is_alive():
            if getattr(self, "_fprev_on", False):
                self._fprev_dirty = show   # a shown preview is busy: done once the worker is free (see _feather_done)
            return
        try:
            req = self._request()
        except (tk.TclError, ValueError) as e:
            self._status(f"Invalid value: {e}", error=True)
            return
        self._fprev_dirty = None
        self.b_fprev.configure(state="disabled")

        def work():
            try:
                msg = self.bridge.show_feather(req) if show else self.bridge.hide_feather()
                self.events.put(("feather", (self.bridge.feather_shown, msg, False)))
            except (BridgeError, PhotoCraftError) as e:
                self.events.put(("feather", (self.bridge.feather_shown, f"Error: {e}", True)))
            except Exception as e:
                self.events.put(("feather", (self.bridge.feather_shown, f"Unexpected error: {type(e).__name__}: {e}", True)))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _refresh_feather_preview(self):
        """A setting changed while the preview is shown: show it anew, once the slider has stopped for a moment."""
        if not getattr(self, "_fprev_on", False):
            return
        if getattr(self, "_fprev_after", None):
            self.root.after_cancel(self._fprev_after)
        self._fprev_after = self.root.after(400, lambda: (setattr(self, "_fprev_after", None),
                                                          self.toggle_feather_preview(show=True)))

    def _feather_done(self, shown: bool, msg: str, error: bool):
        self._fprev_on = shown
        self.b_fprev.configure(text="Hide feather" if shown else "Show feather", state="normal")
        if msg:
            self._status(msg, error=error)
        pending, self._fprev_dirty = getattr(self, "_fprev_dirty", None), None
        if pending is not None and shown:    # the slider moved (show anew) or Hide was clicked while it was busy
            self.toggle_feather_preview(show=pending)

    def stop(self):
        if self.worker and self.worker.is_alive():
            self.bridge.cancel()
            self._status("Cancelling…")

    def _poll(self):
        frame = None                # the newest live preview frame of this round (older ones are skipped)
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "preview":
                    frame = data
                elif kind == "progress":
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
                    frame = None
                    self._hide_preview()            # the result is in PhotoCraft now (user 29.10., option A)
                    ok = not data.startswith(("Error", "Cancel", "Unexpected"))
                    self._reset_progress(done=ok, text=data if ok else "")      # the success line sits above the bar, nothing below it
                    self._status("" if ok else data, error=data.startswith(("Error", "Unexpected")))
                    self._running = False
                    self.b_go.configure(state="normal")
                    self.w_variants.configure(state="disabled" if self._run_mode() in SCALE_MODES else "normal")
                    self.b_undo.configure(state="normal")
                    self.b_redo.configure(state="normal")
                    self.b_stop.configure(state="disabled")
                    self._history_end(ok)
                elif kind == "vgl":
                    self._last_vgl = str(data or "")      # not shown in the window; the copy button next to the LLM checkbox takes it
                    self.b_copy.configure(state="normal" if self._last_vgl.strip() else "disabled")
                    if getattr(self, "_hist_run", None):
                        self._hist_run["llm"] = self._last_vgl.strip()
                elif kind == "refresh":
                    self._apply_refresh(data)
                elif kind == "feather":
                    self._feather_done(*data)
        except queue.Empty:
            pass
        if frame is not None:
            self._show_preview(frame)
        self.root.after(100, self._poll)

    def _show_preview(self, im):
        """A live preview frame: as wide as the window (at most square), above the status line. The area appears with the
        first frame and the window grows with it; minimised, nothing is shown."""
        if getattr(self, "_minimized", False):
            return
        try:
            w = max(int(self.root.winfo_width()), self._px(MIN_W)) - self._px(20)
        except (tk.TclError, TypeError, ValueError):
            w = self._px(MIN_W - 20)
        from PIL import ImageOps
        shown = ImageOps.contain(im, (w, w))
        self._preview_photo = icons.photo(self.root, None, "", 0, image=shown)     # Tk drops an image Python no longer holds
        self.lbl_preview.configure(image=self._preview_photo)
        if not self.f_preview.winfo_manager():
            self.f_preview.pack(fill="x", padx=10, pady=(6, 0), before=self.f_status)
            self._fit_height()

    def _hide_preview(self):
        if self.f_preview.winfo_manager():
            self.f_preview.pack_forget()
            self.lbl_preview.configure(image="")
            self._preview_photo = None
            self._fit_height()

    def _reset_progress(self, done: bool = False, text: str = ""):
        self._bar_value = 1.0 if done else 0.0
        self.pb.configure(value=self._bar_value)
        full = (text or "Done") if done else ""
        word, rest = (full[:4], full[4:]) if full.startswith("Done") else (full, "")      # only the word "Done" is green
        self.v_pl.set(word)
        self._set_rest(rest)
        self._pl_style("Done.TLabel" if done else "Muted.TLabel")
        self._show_pl_line()

    def _show_pl_line(self):
        """The line above the bar takes room only while it says something (the step, or "Done"): no empty line before the
        first run."""
        top = getattr(self, "f_pl_top", None)
        if top is None:
            return
        shown = bool(top.winfo_manager())
        if self.v_pl.get() and not shown:
            top.pack(fill="x", before=self.pb)
        elif not self.v_pl.get() and shown:
            top.pack_forget()

    def _set_rest(self, text: str):
        v = getattr(self, "v_pl_rest", None)
        if v is not None and v.get() != text:
            v.set(text)

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
            self._show_pl_line()
        self._set_rest("")
        self._pl_style("Muted.TLabel")
        if fraction is not None and fraction > self._bar_value:
            self._bar_value = round(fraction, 3)
            self.pb.configure(value=self._bar_value)
