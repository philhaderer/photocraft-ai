"""The prompt field: editor keys, hints, ready-made prompts, enhance and negative boxes. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from . import manifest, styles
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
        """The "LLM prompt enhancement" row (with the copy button): not in Expand, Remove, Refine and Upscale (NO_LLM_MODES). It sits directly under the negative
        prompt, above the Upscale factor and the LoRA switches (user 30.10.)."""
        shown = bool(self.f_enh.winfo_manager())
        if on and not shown:
            self.f_enh.pack(fill="x", padx=10, pady=(6, 0), after=self.f_neg)
        elif not on and shown:
            self.f_enh.pack_forget()
        if on != shown and getattr(self, "_sized", False):
            self._fit_height()

    def _below_prompt(self):
        """What the next box under the prompt goes after: the LLM row when it is shown, else the negative prompt."""
        return self.f_enh if self.f_enh.winfo_manager() else self.f_neg

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
        text = (spec.prompt_tip if spec and spec.prompt_tip else "") or (EXPAND_HINT if mode == "outpaint" else "")
        on = bool(text)
        self._hint_text = text
        self._update_llm_button()
        self._update_styles_button()
        self.t_prompt.configure(highlightbackground=ACCENT if on else "#454545", highlightthickness=2 if on else 1)
        if on:
            self.lbl_hint.configure(text=text)
            self.f_hint.pack(fill="x", padx=10, after=self.grip)      # the text with its info icon (gui.py)
        else:
            self.f_hint.pack_forget()
        b = getattr(self, "b_describe", None)
        if b is not None:
            if self._needs_description():
                b.pack(anchor="w", padx=10, pady=(4, 0), after=self.f_hint)
            else:
                b.pack_forget()

    def _needs_description(self) -> bool:
        """Krea 2 / MOSS Expand: the model needs a prompt (an empty one fills the margin with unrelated things)."""
        m = self._model()
        spec = m.modes.get(self.v_mode.get()) if m else None
        return bool(spec and spec.describe)

    def describe_scene(self):
        """The Describe button: Qwen 3.5 9B describes the surroundings of the picture in PhotoCraft (Bridge.describe_scene);
        the text replaces the field's content in one undo step (Ctrl+Z in the field brings the old text back)."""
        import threading
        if getattr(self, "_describing", False) or (self.worker and self.worker.is_alive()):
            return
        self._describing = True
        self.b_describe.configure(state="disabled")
        self._status("Describing the surroundings …")
        box: dict = {}

        def work():
            try:
                box["text"] = self.bridge.describe_scene()
            except Exception as e:   # PhotoCraft or ComfyUI not running, no text model ...
                box["error"] = str(e)

        threading.Thread(target=work, daemon=True).start()

        def check():
            if "text" not in box and "error" not in box:
                self.root.after(200, check)
                return
            self._describing = False
            self.b_describe.configure(state="normal")
            if "error" in box:
                self._status("Describe failed: " + box["error"], error=True)
                return
            t = self.t_prompt
            t.edit_separator()
            t.delete("1.0", "end")
            t.insert("1.0", box["text"])
            t.edit_separator()
            self._status("Described. Edit the text as you like, then Generate.")
        self.root.after(200, check)

    def _llm_file(self) -> str:
        """The text model file the LLM button uses: the first of the model's describe writers that ComfyUI lists ("" = none)."""
        m = self._model()
        if m is None or self.inv is None:
            return ""
        for name in manifest.describe_writers(m.key):
            found = self.inv.found(name)
            if found:
                return found
        return ""

    def _update_llm_button(self):
        """The LLM button is grey while no function is chosen, the prompt is switched off (Remove object) or the model's text
        model is missing; the tooltip says which file."""
        b = getattr(self, "b_llm", None)
        if b is None:
            return
        m = self._model()
        off = str(self.t_prompt.cget("state")) == "disabled"
        if m is None or off:
            b.configure(state="disabled")
            self.tt_llm.text = LLM_TIP
        elif self.inv is not None and not self._llm_file():
            b.configure(state="disabled")
            self.tt_llm.text = LLM_TIP + f"\n\nNeeds {manifest.describe_writers(m.key)[0]}: download it in the settings (gear)."
        else:
            b.configure(state="normal")
            self.tt_llm.text = LLM_TIP

    def describe_canvas(self):
        """The LLM button: the model's text model describes the picture in PhotoCraft (Bridge.describe_canvas); the text goes
        to the end of the prompt after a line break, in one undo step (Ctrl+Z in the field takes it away)."""
        import threading
        if getattr(self, "_describing", False) or (self.worker and self.worker.is_alive()):
            return
        clip = self._llm_file()
        self._describing = True
        self.b_llm.configure(state="disabled")
        self._status("Describing the picture …")
        box: dict = {}

        def work():
            try:
                box["text"] = self.bridge.describe_canvas(clip)
            except Exception as e:   # PhotoCraft or ComfyUI not running, no text model ...
                box["error"] = str(e)

        threading.Thread(target=work, daemon=True).start()

        def check():
            if "text" not in box and "error" not in box:
                self.root.after(200, check)
                return
            self._describing = False
            self._update_llm_button()
            if "error" in box:
                self._status("Describe failed: " + box["error"], error=True)
                return
            t = self.t_prompt
            t.edit_separator()
            if t.get("1.0", "end").strip():
                t.insert("end-1c", "\n" + box["text"])
            else:
                t.insert("1.0", box["text"])
            t.edit_separator()
            self._status("Described. The text is at the end of the prompt.")
        self.root.after(200, check)

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
        """Ready-made prompts of a mode (Flux 2 refine): small switches next to "Prompt" that put the text into the field (the
        look of the Upscale factor, user 29.10.: PhotoCraft has no round radio buttons); the chosen one is orange."""
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
                                 command=lambda t=text: self._insert_prompt(t), style="Small.Toolbutton")
            rb.pack(side="left", padx=(0, 4))
            Tooltip(rb, tip)

    def _insert_prompt(self, text: str):
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        t.delete("1.0", "end")
        t.insert("1.0", text)

    # ---------- Styles (styles.json) ----------

    def _build_styles_menus(self):
        """One menu per mode that has styles: a submenu per group, an entry per style (its name). The whole text shows in a box
        right of the menu while the mouse is on an entry (user 1.11.; a menu entry has no tooltip of its own)."""
        self._styles = styles.load()
        self.m_styles: dict = {}
        self._style_texts: dict = {}        # (submenu, entry number) -> the style's text
        self._style_tip = None
        self._style_menus: list = []        # kept, so the submenus (and their names) stay alive
        kw = dict(tearoff=0, bg=PANEL, fg=FG, activebackground=ACCENT, activeforeground="#1b1b1b", bd=0, font=font(10))
        for mode, groups in self._styles.items():
            top = tk.Menu(self.root, **kw)
            for g in groups:
                sub = tk.Menu(top, **kw)
                self._style_menus.append(sub)
                for i, s in enumerate(g["styles"]):
                    sub.add_command(label=s["name"], command=lambda t=s["text"]: self._apply_style(t))
                    self._style_texts[(str(sub), i)] = s["text"]
                sub.bind("<<MenuSelect>>", lambda e, m=sub: self._style_preview(m), add="+")
                sub.bind("<Unmap>", lambda e: self._style_tip_hide(), add="+")
                top.add_cascade(label=g["name"], menu=sub)
            top.bind("<<MenuSelect>>", lambda e: self._style_tip_hide(), add="+")
            self.m_styles[mode] = top

    def _update_styles_button(self):
        """The Styles button is there only in a mode that has styles (Text to image), also in Easy Mode (user 1.11.); it sits left
        of the LLM button, or left of the bin while Easy Mode hides the LLM button."""
        b = getattr(self, "b_styles", None)
        if b is None:
            return
        want = self.v_mode.get() in self.m_styles
        if want and not self._styles_shown:
            b.pack(side="right", padx=(0, 6), after=self.b_llm if self.b_llm.winfo_manager() else self.b_clear)
            self._styles_shown = True
        elif not want and self._styles_shown:
            b.pack_forget()
            self._styles_shown = False

    def _styles_menu(self):
        """A click on the Styles button: the groups, opening under the button."""
        m = self.m_styles.get(self.v_mode.get())
        if m is None or str(self.t_prompt.cget("state")) == "disabled":
            return
        b = self.b_styles
        try:
            m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            try:
                m.grab_release()
            except Exception:
                pass
            self._style_tip_hide()

    def _apply_style(self, text: str):
        """A style entry REPLACES the prompt (user 1.11.), in one undo step: Ctrl+Z in the field brings the old text back."""
        t = self.t_prompt
        if str(t.cget("state")) == "disabled":
            return
        auto = t.cget("autoseparators")      # Tk would otherwise split delete + insert into two undo steps
        t.configure(autoseparators=False)
        try:
            t.edit_separator()
            t.delete("1.0", "end")
            t.insert("1.0", text)
            t.edit_separator()
        finally:
            t.configure(autoseparators=auto)
        self.v_pchoice.set("")
        t.focus_set()
        self._status("Style set as the prompt. Ctrl+Z in the field brings the old text back.")

    def _style_text_at(self, menu, active):
        """The text of entry number `active` of a style submenu ("" for none)."""
        return self._style_texts.get((str(menu), active), "") if isinstance(active, int) else ""

    def _style_preview(self, menu):
        """<<MenuSelect>> of a group menu: the whole text of the entry under the mouse in a small box right of the menu (left
        of it when there is no room)."""
        self._style_tip_hide()
        try:
            text = self._style_text_at(menu, menu.index("active"))
            if not text:
                return
            # a native Windows menu reports no position (x = y = 0, width 1: the box sat at the screen's top left, user 1.11.),
            # so the box goes level with the mouse and beside the menu's real window (found under the mouse)
            px, py = self.root.winfo_pointerx(), self.root.winfo_pointery()
            left, right = self._menu_span(menu, px, py)
            x, y = right + 4, py - 12
            tip = tk.Toplevel(self.root)
            tip.wm_overrideredirect(True)
            tk.Label(tip, text=text, justify="left", wraplength=340, background="#ffffe0", foreground="#000000",
                     relief="solid", borderwidth=1, padx=6, pady=4, font=font(9)).pack()
            tip.update_idletasks()
            vx0, vy0, vx1, vy1 = self._monitor_at(px, py)
            if x + tip.winfo_reqwidth() > vx1:
                x = max(vx0, left - tip.winfo_reqwidth() - 4)
            y = max(vy0, min(y, vy1 - tip.winfo_reqheight()))
            tip.wm_geometry(f"+{x}+{y}")
            self._style_tip_pos = (x, y)         # (a tip of a hidden window reports +0+0, so the tests read this)
            tip.wm_attributes("-topmost", True)
            self._style_tip = tip
        except tk.TclError:
            self._style_tip_hide()

    def _monitor_at(self, px: int, py: int) -> tuple:
        """(x0, y0, x1, y1) of the monitor under the point (Windows API); the window may sit on a second monitor, where Tk's
        screen size (the first monitor) is wrong. Falls back to Tk's screen."""
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            u.MonitorFromPoint.restype = wintypes.HANDLE

            class MI(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                            ("dwFlags", wintypes.DWORD)]
            mi = MI()
            mi.cbSize = ctypes.sizeof(MI)
            hm = u.MonitorFromPoint(wintypes.POINT(px, py), 2)       # 2 = the nearest monitor
            if hm and u.GetMonitorInfoW(hm, ctypes.byref(mi)):
                r = mi.rcMonitor
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _menu_span(self, menu, px: int, py: int) -> tuple:
        """(left, right) screen x of a posted menu: Tk's own numbers when it has some, else the window under the mouse (Windows
        API), else a guess around the mouse."""
        try:
            if menu.winfo_width() > 1 and menu.winfo_rootx() > 0:
                return menu.winfo_rootx(), menu.winfo_rootx() + menu.winfo_width()
        except tk.TclError:
            pass
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.windll.user32
            u.WindowFromPoint.argtypes = [wintypes.POINT]
            u.WindowFromPoint.restype = wintypes.HWND
            hwnd = u.WindowFromPoint(wintypes.POINT(px, py))
            rc = wintypes.RECT()
            if hwnd and u.GetWindowRect(hwnd, ctypes.byref(rc)) and rc.left <= px <= rc.right and rc.right - rc.left < 1200:
                return rc.left, rc.right
        except Exception:
            pass
        return px - 100, px + 100

    def _style_tip_hide(self):
        tip, self._style_tip = getattr(self, "_style_tip", None), None
        if tip is not None:
            try:
                tip.destroy()
            except Exception:
                pass

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
