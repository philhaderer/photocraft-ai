"""The prompt field: editor keys, hints, ready-made prompts, enhance and negative boxes. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401


class PromptMixin:
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

    def _show_enhance_box(self, on: bool):
        """The "LLM prompt enhancement" row (with the copy button): not in Expand image."""
        shown = bool(self.f_enh.winfo_manager())
        if on and not shown:
            self.f_enh.pack(fill="x", padx=10, pady=(6, 0), before=self.f_adv)
        elif not on and shown:
            self.f_enh.pack_forget()
        if on != shown and getattr(self, "_sized", False):
            self._fit_height()

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

    def _clear_prompt(self):
        """The bin next to "Prompt": empties the field (one undo step, so Ctrl+Z in the field brings the text back)."""
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        t.edit_separator()
        t.delete("1.0", "end")
        t.edit_separator()
        self.v_pchoice.set("")
        t.focus_set()

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

    def _show_negative(self):
        opened = bool(self.v_neg_open.get())
        self.btn_neg.configure(text="Negative prompt", compound="left",
                               image=self._icon("chevron-down" if opened else "chevron-right", MUTED))
        if opened:
            self.neg_body.pack(fill="x", pady=(4, 0))
        else:
            self.neg_body.pack_forget()

    def _toggle_negative(self):
        self.v_neg_open.set(not self.v_neg_open.get())
        self._show_negative()
        self._fit_height()
