"""The extra LoRA rows and the LoRA switch. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401


class LoraMixin:
    # ---------- extra LoRAs ----------

    LORA_MAX = 4

    LORA_HINTS = {"qwen": ("qwen",), "flux2": ("flux 2", "flux2", "flux_2"), "flux3": ("flux 3", "flux3", "flux_3"),
                  "moss": ("moss",), "fibo": ("fibo", "bria")}

    def _lora_choices(self, typed: str = "") -> list[str]:
        """The LoRA list for a drop-down: this model's folder first, filtered by what was typed (all words, any case)."""
        hints = self.LORA_HINTS.get(self.v_model.get(), ())
        names = sorted(self.all_loras, key=lambda n: (not any(h in n.lower() for h in hints), n.lower()))
        words = typed.lower().split()
        return [n for n in names if all(w in n.lower() for w in words)]

    def _add_lora_row(self, name: str = "", strength: float = 1.0):
        if len(self.lora_rows) >= self.LORA_MAX:
            return
        row = ttk.Frame(self.f_xl_rows)
        row.pack(fill="x", pady=1)
        row.columnconfigure(0, weight=1)
        v_name, v_str = tk.StringVar(value=name), tk.StringVar(value=f"{float(strength):g}")   # text: "0,2" can be typed
        rec = {"frame": row, "name": v_name, "strength": v_str, "list": None, "box": None}
        ent = ttk.Entry(row, textvariable=v_name)
        ent.grid(row=0, column=0, sticky="ew")
        rec["entry"] = ent
        btn = ttk.Button(row, image=self._icon("chevron-down", MUTED), style="Link.TButton", command=lambda: self._lora_toggle(rec))
        btn.grid(row=0, column=1, padx=(2, 0))
        rec["btn"] = btn
        sp = ttk.Spinbox(row, textvariable=v_str, from_=0.0, to=1.5, increment=0.05, width=5)
        sp.grid(row=0, column=2, padx=4)
        try:      # numbers only, comma or point (user 28.10.); the arrows and Up/Down step from the typed value
            sp.configure(validate="key", validatecommand=(sp.register(number_typed_ok), "%d", "%S", "%P"))
        except (AttributeError, tk.TclError):
            pass
        for ev in ("<FocusOut>", "<Return>", "<Up>", "<Down>", "<ButtonPress-1>"):
            sp.bind(ev, lambda e, r=rec: self._lora_strength_text(r), add="+")
        rm = ttk.Button(row, image=self._icon("remove", MUTED), style="Link.TButton", command=lambda: self._remove_lora_row(rec))
        rm.grid(row=0, column=3)
        # typing opens a list under the row that narrows with every key; a click (or Down, Enter) takes the entry
        ent.bind("<KeyRelease>", lambda e: self._lora_key(rec, e))
        ent.bind("<Down>", lambda e: self._lora_focus_list(rec))
        ent.bind("<Escape>", lambda e: (self._lora_hide(rec), "break")[1])
        Tooltip(rm, "Remove this LoRA")
        Tooltip(btn, "Show all LoRAs")
        Tooltip(ent, "Type to search, click a LoRA to take it.")
        self.lora_rows.append(rec)
        self.b_addlora.configure(state="normal" if len(self.lora_rows) < self.LORA_MAX else "disabled")

    def _lora_key(self, rec: dict, e):
        if getattr(e, "keysym", "") in ("Return", "Escape", "Tab", "Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return
        self._lora_show(rec, rec["name"].get())

    def _lora_toggle(self, rec: dict):
        if rec.get("box") is not None:
            self._lora_hide(rec)
        else:
            self._lora_show(rec, "")

    def _lora_show(self, rec: dict, typed: str = ""):
        """The list under a LoRA row: the matches for what was typed (scrollable; a click takes one)."""
        try:
            names = self._lora_choices(typed)[:400]
            if not names:
                self._lora_hide(rec)
                return
            box = rec.get("box")
            if box is None:
                box = ttk.Frame(self.f_xl_rows)
                lb = tk.Listbox(box, height=8, exportselection=False, activestyle="none", bg=PANEL, fg=FG,
                                selectbackground=ACCENT, selectforeground="#1b1b1b", relief="flat", highlightthickness=1,
                                highlightbackground="#454545", font=font(9))
                sb = ttk.Scrollbar(box, orient="vertical", command=lb.yview)
                lb.configure(yscrollcommand=sb.set)
                sb.pack(side="right", fill="y")
                lb.pack(side="left", fill="both", expand=True)
                box.pack(fill="x", after=rec["frame"])
                lb.bind("<ButtonRelease-1>", lambda e: self._lora_pick(rec))
                lb.bind("<Return>", lambda e: self._lora_pick(rec))
                lb.bind("<Escape>", lambda e: (self._lora_hide(rec), rec["entry"].focus_set(), "break")[2])
                rec["box"], rec["list"] = box, lb
            lb = rec["list"]
            lb.configure(height=max(1, min(8, len(names))))
            lb.delete(0, "end")
            for n in names:
                lb.insert("end", n)
            if self._sized:
                self._fit_height()
        except Exception as e:      # shown instead of silently doing nothing
            self._status(f"LoRA list: {e}", error=True)

    def _lora_focus_list(self, rec: dict):
        if rec.get("box") is None:
            self._lora_show(rec, rec["name"].get())
        lb = rec.get("list")
        if lb is not None:
            lb.focus_set()
            lb.selection_set(0)
            lb.activate(0)
        return "break"

    def _lora_pick(self, rec: dict):
        lb = rec.get("list")
        if lb is None:
            return
        sel = lb.curselection()
        if sel:
            rec["name"].set(lb.get(sel[0]))
        self._lora_hide(rec)
        rec["entry"].focus_set()

    def _lora_hide(self, rec: dict):
        box = rec.get("box")
        if box is not None:
            box.destroy()
            rec["box"] = rec["list"] = None
            if self._sized:
                self._fit_height()

    def _lora_outside(self, e):
        """A click anywhere but in a LoRA row or its list closes the lists."""
        for rec in list(self.lora_rows):
            if rec.get("box") is None:
                continue
            w = str(e.widget)
            if w.startswith(str(rec["box"])) or w in (str(rec["entry"]), str(rec["btn"])):
                continue
            self._lora_hide(rec)

    def _remove_lora_row(self, rec: dict):
        if rec in self.lora_rows:
            self.lora_rows.remove(rec)
            self._lora_hide(rec)
            rec["frame"].destroy()
            if not self.lora_rows:
                # Tk keeps the height of a frame whose last packed child is gone: the empty line stayed. A new
                # height makes it shrink (1 px, nothing visible).
                self.f_xl_rows.configure(height=1)
        self.b_addlora.configure(state="normal")
        self._fit_height()

    def _loras(self) -> list[list]:
        """What the rows say: [[file, strength], ...] for the rows with a name."""
        out = []
        for r in self.lora_rows:
            n = r["name"].get().strip()
            if n:
                out.append([n, self._lora_strength(r)])
        return out

    @staticmethod
    def _lora_strength(rec: dict) -> float:
        """A LoRA row's strength: comma or point, kept in 0..1.5; nothing usable typed = 1.0."""
        v = parse_number(rec["strength"].get())
        return 1.0 if v is None else round(min(1.5, max(0.0, v)), 2)

    def _lora_strength_text(self, rec: dict):
        """The strength field shows the number as the spin arrows read it ("0,2" -> "0.2")."""
        text = rec["strength"].get()
        if parse_number(text) is not None or not text.strip():
            v = f"{self._lora_strength(rec):g}"
            if v != text:
                rec["strength"].set(v)

    def _set_loras(self, items):
        for r in list(self.lora_rows):
            self._remove_lora_row(r)
        for n, st in (items or [])[: self.LORA_MAX]:
            self._add_lora_row(str(n), float(st))

    def _on_lora_str(self, _value=None):
        self.lbl_lora_str.configure(text=f"{float(self.v_lora_str.get()):.2f}")

    def _update_options_box(self, has_lora: bool, stages: list):
        """The box with the workflow's LoRA / stage switches is shown only when there is something in it."""
        want = bool(has_lora or stages)
        shown = bool(self.f_opts.winfo_manager())
        if want and not shown:
            self.f_opts.pack(fill="x", padx=10, pady=4, after=self.f_scale if self.f_scale.winfo_manager() else self._below_prompt())
        elif not want and shown:
            self.f_opts.pack_forget()
        if want != shown and getattr(self, "_sized", False):
            self._fit_height()

    def _lora_label(self) -> str:
        """The checkbox text: the workflow names its LoRA (pc_lora_label in the _meta of the pc:lora node)."""
        wf = self.v_workflow.get()
        if wf != BUILTIN:
            try:
                for w in resolve(self.workflows_dir / wf):
                    for nid in lora_switches(load_template(w)):
                        label = str(load_template(w)[nid].get("_meta", {}).get("pc_lora_label", "")).strip()
                        if label:
                            return label
            except (OSError, ValueError, KeyError):
                pass
        return "LoRA"

    def _has_lora_switch(self) -> bool:
        """True when the selected workflow (or one of a group) has a speed LoRA the window can switch off (pc:lora)."""
        wf = self.v_workflow.get()
        if wf == BUILTIN:
            return False
        try:
            return any(lora_switches(load_template(w)) for w in resolve(self.workflows_dir / wf))
        except (OSError, ValueError, KeyError):
            return False
