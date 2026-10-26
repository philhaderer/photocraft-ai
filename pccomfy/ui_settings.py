"""Settings overlay, model detection in the window, greyed tabs (lane L1, PLAN.md tasks 6 to 8).

``SettingsMixin`` stands first in ``App``'s bases, so its methods wrap the ones of the other mixins (it calls ``super()``):

* ``refresh`` / ``_apply_refresh``: also read ComfyUI's installed files (in a thread, the result arrives as a "refresh" event);
* ``_update_mode_radios``: a mode whose files are missing is greyed out, its tooltip says what is missing;
* ``_on_model``: a click on a greyed tab opens the settings instead of switching to it;
* ``generate``: the preflight; a missing file stops the run with one clear line (file, folder, link).

The gear button next to the tabs opens the overlay: what is installed per tab, links to download, "link a file of another
name", the extra_model_paths.yaml, and the credits. All decisions live in ``inventory.py`` and ``manifest.py`` (no Tk there).
"""
from __future__ import annotations

import webbrowser

from . import inventory, manifest
from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401

_LABELS = dict(MODE_LABELS)      # noqa: F405
EMPTY_TEXT = {"choose": "Choose a model", "none_linked": "Link your model in the settings"}
STATE_TEXT = {"ready": "ready", "partial": "some functions need files", "missing": "files missing"}


class SettingsMixin:
    inv = None                  # inventory.Inventory of the last successful reading (None = ComfyUI not read / not reachable)
    _inv_error = ""
    _yaml_sections: list = []
    _disk: dict = {}
    _settings_win = None
    _settings_focus = None
    _last_model = ""
    _refreshing = False         # inside StateMixin._apply_refresh (its "open on the first model" step is not wanted here)
    _startup_checked = False    # the first reading after start has been looked at (a last model that is gone is let go once)

    # ---------- build (one call at the end of App._build) ----------

    def _build_settings(self, foot):
        """The gear button at the right end of the footer row (the one with the connection dots, Refresh and Reset)."""
        self._last_model = self.v_model.get()
        style = ttk.Style()
        style.configure("Missing.Tab.Toolbutton", foreground=NA_RED)      # a tab that is not available: red text, the background of an inactive tab
        self.b_gear = ttk.Button(foot, image=self._icon("gear"), style="Icon.TButton", command=self.open_settings)
        self.b_gear.pack(side="right")
        Tooltip(self.b_gear, "Settings: which model files ComfyUI has, links to get the missing ones, ComfyUI folders, credits.")
        style.configure("Empty.TLabel", foreground=MUTED, font=(FONT, 11))
        self.v_empty = tk.StringVar(value="")
        self.lbl_empty = ttk.Label(self.root, textvariable=self.v_empty, style="Empty.TLabel", anchor="center", justify="center",
                                   wraplength=self._px(MIN_W - 40))
        self._foot_hidden = False
        self._apply_start_state(fit=False)

    # ---------- reading ComfyUI ----------

    def refresh(self):
        super().refresh()
        self._detect_async()

    def _detect_async(self, reread: bool = True):
        mapping, path, comfy = cfgmod.model_map(), cfgmod.extra_paths_file(), self.comfy

        def work():
            res = {"_detect": True}
            if reread:
                try:
                    res["_inv"], res["_inv_error"] = inventory.fetch(comfy, mapping), ""
                except ComfyError as e:
                    res["_inv"], res["_inv_error"] = None, str(e)
            sections = inventory.read_extra_paths(path) if path else []
            res["_yaml"], res["_disk"] = sections, (inventory.find_on_disk(sections) if sections else {})
            self.events.put(("refresh", res))
        threading.Thread(target=work, daemon=True).start()

    def _apply_refresh(self, info):
        if not info.get("_detect"):
            self._refreshing = True
            try:
                super()._apply_refresh(info)
            finally:
                self._refreshing = False
            return
        self._yaml_sections, self._disk = info.get("_yaml", []), info.get("_disk", {})
        if "_inv" in info:
            self._set_inventory(info["_inv"], info.get("_inv_error", ""))
        elif self._settings_win is not None:
            self._settings_fill()

    def _set_inventory(self, inv, err: str = ""):
        self.inv, self._inv_error = inv, err
        self._let_go_unavailable_model()
        self.comfy.name_fixer = inv.apply_names if inv is not None else None    # a linked or differently written file name is renamed when a graph is queued
        self._update_tabs()
        self._apply_start_state()
        try:
            self._update_mode_radios()
        except (AttributeError, tk.TclError):      # the window is still being built
            pass
        if self._settings_win is not None:
            self._settings_fill()

    # ---------- tabs and modes ----------

    def _tab_extra(self, st: "inventory.Status") -> str:
        if st.state == "partial":
            return "\n".join(inventory.tooltip_text(s, _LABELS.get(mode, mode)) for mode, s in st.detail.items())
        if st.state == "missing":
            return inventory.tooltip_text(st)
        if st.optional_missing:
            return "Not installed (optional): " + ", ".join(f.name for f in st.optional_missing[:3])
        return ""

    def _update_tabs(self):
        tts = getattr(self, "tt_tabs", {})
        for m in models.MODELS:
            rb = self.rb_tabs.get(m.key)
            if rb is None:
                continue
            st = self.inv.tab_status(m.key) if self.inv is not None else None
            rb.configure(style="Missing.Tab.Toolbutton" if (st is not None and st.state == "missing") else "Tab.Toolbutton")
            tt = tts.get(m.key)
            if tt is not None:
                extra = self._tab_extra(st) if st is not None else ""
                tt.text = m.tip + (("\n\n" + extra) if extra else "")

    def _update_mode_radios(self):
        super()._update_mode_radios()
        m = self._model()
        if m is None or self.inv is None:
            return
        for key in m.modes:
            s = self.inv.mode_status(m.key, key)
            if s.state == "missing":
                self.rb_modes[key].configure(state="disabled")
                self.tt_modes[key].text += "\n\n" + inventory.tooltip_text(s, _LABELS.get(key, key))

    # ---------- no model chosen ----------

    def start_state(self) -> str:
        """"none_linked": ComfyUI was read and not one tab can run; "choose": no tab is chosen; "": a model is chosen. The window
        shows no parameters in the first two (the look of those states is decided in FRAGEN.md / docs, see entscheidungen)."""
        if self.inv is not None and all(self.inv.tab_status(m.key).state == "missing" for m in models.MODELS):
            return "none_linked"
        return "choose" if (not self.v_model.get() and self.v_workflow.get() in ("", BUILTIN)) else ""      # (a workflow of your own is no "no model")

    def _apply_start_state(self, fit: bool = True):
        """Show what belongs to the state: a model is chosen = everything; none chosen = the tabs, one sentence, the footer; no model
        linked = only the sentence and the gear (the footer's connection dots, Refresh and Reset go too). Stacking order stays
        tabs, sentence, body, status line (the footer is packed at the bottom)."""
        state = self.start_state()
        self.v_empty.set(EMPTY_TEXT.get(state, ""))
        for w in (self.f_tabs, self.lbl_empty, self.f_scrollbox):
            w.pack_forget()
        if state != "none_linked":
            self.f_tabs.pack(fill="x", padx=10, pady=(8, 2), before=self.f_status)
        if state:
            self.lbl_empty.pack(fill="x", padx=10, pady=(26, 22), before=self.f_status)
        else:
            self.f_scrollbox.pack(fill="x", before=self.f_status)     # the body sits in its scroll box (gui.py)
        hide_foot = state == "none_linked"
        if hide_foot != self._foot_hidden:
            self._foot_hidden = hide_foot
            for w in (self.lbl_conn, self.b_refresh, self.b_reset):
                w.pack_forget()
            if not hide_foot:
                self.lbl_conn.pack(side="left")
                self.b_refresh.pack(side="left", padx=(8, 0))
                self.b_reset.pack(side="left", padx=(6, 0))
        if fit and getattr(self, "_sized", False):
            self._fit_height()

    def _let_go_unavailable_model(self):
        """At start only: the model of the last session may have lost its files meanwhile. Then no tab is chosen (instead of a
        broken one). Later readings never take the tab away under the user's hands: the preflight explains a missing file."""
        if self._startup_checked or self.inv is None:
            return
        self._startup_checked = True
        m = self._model()
        if m is not None and self.inv.tab_status(m.key).state == "missing":
            self.v_model.set("")
            self.v_workflow.set(BUILTIN)        # _sync_model would pick the model of the workflow again
            self._last_model = ""
            self._status(f"{m.label} is not available (model files missing). Choose a model.")

    def _on_model_core(self):
        if self._refreshing and not self._last_model:
            self.v_model.set("")                # first start: StateMixin would open on the first model; the user chooses
            return
        key, prev = self.v_model.get(), self._last_model
        if key and self.inv is not None and key != prev and self.inv.tab_status(key).state == "missing":
            self.v_model.set(prev)              # a tab that is not available does not open: its settings do
            self.open_settings(focus=key)
            return
        self._last_model = self.v_model.get()
        if key:                                  # the last model comes back at the next start (state.json, like the other settings)
            self.state["model"] = key
            cfgmod.save_state(self.state)
        super()._on_model()

    def _on_model(self):
        self._on_model_core()
        self._apply_start_state()

    # ---------- presets ----------

    def preset_blocked(self, settings: dict) -> str:
        """For a preset: "" when its model and mode can run, else a short note ("Flux 3 Klein Edit is missing files ..."). The preset
        loader (gui_state.py, see docs/entscheidungen-L1.md) uses it to leave the model out and say why."""
        wf = settings.get("workflow") if isinstance(settings, dict) else None
        m = models.model_for_workflow(wf) if wf and wf != BUILTIN else None
        if m is None or self.inv is None:
            return ""
        mode = settings.get("mode")
        st = self.inv.mode_status(m.key, mode) if mode in m.modes else self.inv.tab_status(m.key)
        if st.state != "missing":
            return ""
        names = [f.name for f in st.missing] + list(st.nodes)
        return f"{m.label} is missing files: {', '.join(names[:2])}{' ...' if len(names) > 2 else ''} (see settings)"

    # ---------- preflight ----------

    def _reread_inventory(self):
        """A fresh reading, in the calling thread (only used when the cached one says something is missing)."""
        try:
            return inventory.fetch(self.comfy, cfgmod.model_map())
        except ComfyError:
            return None

    def _preflight(self) -> list[str]:
        m = self._model()
        if m is None or self.inv is None:
            return []
        mode = self.v_mode.get()
        lines = inventory.preflight(self.inv, m.key, mode)
        if lines:       # the cached reading may be old (a file was copied and ComfyUI restarted since): look again first
            fresh = self._reread_inventory()
            if fresh is not None:
                self._set_inventory(fresh)
                lines = inventory.preflight(fresh, m.key, mode)
        return lines

    def generate(self):
        if self.start_state():
            self._status("Choose a model first.")      # Ctrl+Enter must not run with nothing chosen
            return
        lines = self._preflight()
        if lines:
            self._status(inventory.short_message(lines, self._model().label), error=True)
            return
        super().generate()

    # ---------- the overlay: content as plain data (tested without Tk) ----------

    def _settings_segments(self) -> list[tuple]:
        """The overlay text as (text, style, url) pieces; style is head / ok / bad / muted / note / link."""
        seg: list[tuple] = []
        add = lambda text, style="", url="": seg.append((text, style, url))  # noqa: E731
        if self.inv is None:
            add("ComfyUI could not be read.\n", "bad")
            add((self._inv_error or "Not connected yet.") + "\nStart ComfyUI, then press Refresh.\n\n", "muted")
        else:
            add("Installed models\n", "head")
            add("ComfyUI reads its model folders only when it starts: after copying a file, restart ComfyUI and press Refresh.\n\n", "muted")
            for row in self.inv.rows():
                st = row["status"]
                mark = {"ready": ("● ", "ok"), "partial": ("◐ ", "note"), "missing": ("○ ", "bad")}[st.state]
                add(mark[0], mark[1])
                add(row["label"], "head")
                add("  " + STATE_TEXT[st.state] + ("   ◀" if row["key"] == self._settings_focus else "") + "\n", "muted")
                for f, found, level in row["files"]:
                    if found is not None:
                        add("    ✓ ", "ok")
                        add(f.name + ("" if found == f.name else f"  (as {found})") + ("   optional" if level == "optional" else "") + "\n", "muted")
                        continue
                    add("    ✗ ", "bad" if level == "required" else "note")
                    add(f.name, "")
                    add(("   optional" if level == "optional" else "") + f"   → ComfyUI\\{f.target}", "muted")
                    if f.url:
                        add("   ", "")
                        add("download", "link", f.url)
                    add("\n", "")
                    if f.note:
                        add("        " + f.note + "\n", "muted")
                    for p in self._disk.get(f.name, [])[:1]:
                        add(f"        found on disk: {p}  (restart ComfyUI to list it)\n", "note")
                for c in st.nodes:
                    pack = manifest.node_pack(c)
                    add("    ✗ ", "bad")
                    add(f"node {c}", "")
                    if pack:
                        add("   → " + pack[0], "muted")
                        if pack[1]:
                            add("   ", "")
                            add("get it", "link", pack[1])
                    add("\n", "")
                add("\n", "")
        links = cfgmod.model_map()
        add("Linked files (the plugin uses your file for its expected one)\n", "head")
        if links:
            for k, v in sorted(links.items()):
                add(f"    {k}  →  {v}\n", "muted")
        else:
            add("    none. Use the boxes below when a file has another name.\n", "muted")
        add("\n", "")
        add("ComfyUI folders (extra_model_paths.yaml)\n", "head")
        path = cfgmod.extra_paths_file()
        if not path:
            add("    No file chosen. Choose ComfyUI's extra_model_paths.yaml to see where your model folders are.\n", "muted")
        else:
            add(f"    {path}\n", "muted")
            if not self._yaml_sections:
                add("    Nothing readable in it.\n", "bad")
            for sec in self._yaml_sections:
                add(f"    [{sec['name']}]\n", "")
                for key, paths in sec["folders"].items():
                    for p in paths:
                        add(f"      {key}: {p}\n", "muted")
        add("\n", "")
        add("Credits\n", "head")
        for name, what, url in manifest.CONTRIBUTORS:
            add("    ", "")
            add(name, "link", url)
            add(f"  {what}\n", "muted")
        return seg

    def _link_choices(self) -> tuple[list[str], dict]:
        """(the expected file names that can be linked, installed files per kind)."""
        if self.inv is None:
            return [], {}
        mapped = cfgmod.model_map()
        names = []
        for row in self.inv.rows():
            for f, found, _level in row["files"]:
                if (found is None or f.name in mapped) and f.name not in names:
                    names.append(f.name)
        return names, self.inv.lists

    # ---------- the overlay window ----------

    def open_settings(self, focus: str | None = None):
        self._settings_focus = focus
        if self._settings_win is not None:
            try:
                self._settings_win.lift()
                self._settings_fill()
                return
            except tk.TclError:
                self._settings_win = None
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=BG)
        try:
            win.transient(self.root)
            x = self.root.winfo_rootx() + self.root.winfo_width() + 8
            win.geometry(f"{self._px(560)}x{self._px(700)}+{x}+{self.root.winfo_rooty()}")
        except (tk.TclError, TypeError):
            pass
        win.protocol("WM_DELETE_WINDOW", self._settings_close)
        self._settings_win = win
        self._own_settings(win)

        top = ttk.Frame(win)
        top.pack(fill="x", padx=10, pady=(8, 4))
        self.v_set_conn = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.v_set_conn, style="Muted.TLabel").pack(side="left")
        b = ttk.Button(top, text="Refresh", command=self.refresh)
        b.pack(side="right")
        Tooltip(b, "Reads ComfyUI's installed model files and node classes again.")

        link = ttk.Frame(win)
        link.pack(fill="x", side="bottom", padx=10, pady=(4, 8))
        self.v_link_exp, self.v_link_act = tk.StringVar(value=""), tk.StringVar(value="")
        ttk.Label(link, text="Link a file of another name", style="Muted.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self.cb_link_exp = ttk.Combobox(link, textvariable=self.v_link_exp, state="readonly", width=34)
        self.cb_link_act = ttk.Combobox(link, textvariable=self.v_link_act, state="readonly", width=34)
        self.cb_link_exp.grid(row=1, column=0, sticky="ew", pady=2)
        self.cb_link_act.grid(row=2, column=0, sticky="ew", pady=2)
        self.cb_link_exp.bind("<<ComboboxSelected>>", lambda e: self._link_expected_picked())
        link.columnconfigure(0, weight=1)
        bl = ttk.Button(link, text="Link", command=self._link_models)
        bl.grid(row=1, column=1, padx=(6, 0))
        Tooltip(bl, "Use the installed file in the lower box wherever the plugin expects the one in the upper box.")
        bu = ttk.Button(link, text="Unlink", command=self._unlink_model)
        bu.grid(row=2, column=1, padx=(6, 0))
        by = ttk.Button(link, text="Choose extra_model_paths.yaml…", command=self._choose_yaml)
        by.grid(row=3, column=0, sticky="w", pady=(6, 0))
        Tooltip(by, "ComfyUI's extra_model_paths.yaml: shows where your model folders are and which files lie there. Read only.")
        bc = ttk.Button(link, text="Clear", command=lambda: self.settings_set_yaml(""))
        bc.grid(row=3, column=1, padx=(6, 0), pady=(6, 0))

        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=10)
        sb = ttk.Scrollbar(body)
        sb.pack(side="right", fill="y")
        self.t_settings = tk.Text(body, wrap="word", bg=PANEL, fg=FG, relief="flat", borderwidth=0, padx=8, pady=6,
                                  font=(FONT, 10), yscrollcommand=sb.set, cursor="arrow")
        self.t_settings.pack(side="left", fill="both", expand=True)
        sb.configure(command=self.t_settings.yview)
        self._settings_fill()

    def _own_settings(self, win):
        """The settings window behaves like the bridge window: an owned window of it (and so, through it, of PhotoCraft). It lies
        above them, never above other programs, and is hidden, minimised and closed together with them. Never "always on top":
        that would keep it on screen when PhotoCraft is closed or minimised."""
        if not winlink.available():
            return
        try:
            api = winlink.Win32Api()
            top, owner = api.toplevel(win), api.toplevel(self.root)
            if top and owner and api.owner_of(top) != owner:
                api.set_owner(top, owner)
        except Exception:
            pass

    def _settings_close(self):
        win, self._settings_win = self._settings_win, None
        try:
            win.destroy()
        except (tk.TclError, AttributeError):
            pass

    def _settings_fill(self):
        t = self.t_settings
        try:
            top = t.yview()[0]
        except (tk.TclError, TypeError, IndexError):
            top = 0.0
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.tag_configure("head", font=(FONT, 10, "bold"), foreground=FG)
        t.tag_configure("ok", foreground=DONE_GREEN)           # noqa: F405
        t.tag_configure("bad", foreground=ERROR_TEXT)          # noqa: F405
        t.tag_configure("note", foreground=ACCENT)
        t.tag_configure("muted", foreground=MUTED)
        n = 0
        for text, style, url in self._settings_segments():
            tags = (style,) if style and style != "link" else ()
            if style == "link":
                n += 1
                tag = f"link{n}"
                t.tag_configure(tag, foreground=ACCENT, underline=True)
                t.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
                t.tag_bind(tag, "<Enter>", lambda e: t.configure(cursor="hand2"))
                t.tag_bind(tag, "<Leave>", lambda e: t.configure(cursor="arrow"))
                tags = (tag,)
            t.insert("end", text, tags)
        t.configure(state="disabled")
        try:
            t.yview_moveto(top)
        except tk.TclError:
            pass
        conn = "ComfyUI ●" if self.inv is not None else "ComfyUI ○"
        self.v_set_conn.set(conn)
        exp, _lists = self._link_choices()
        self.cb_link_exp["values"] = exp
        if self.v_link_exp.get() not in exp:
            self.v_link_exp.set(exp[0] if exp else "")
        self._link_expected_picked()

    # ---------- link a file of another name ----------

    def _link_expected_picked(self):
        exp = self.v_link_exp.get()
        f = manifest.FILES.get(exp)
        _names, lists = self._link_choices()
        avail = list(lists.get(f.kind, [])) if f is not None else []
        self.cb_link_act["values"] = avail
        mapped = cfgmod.model_map().get(exp)
        self.v_link_act.set(mapped if mapped in avail else "")

    def _link_models(self):
        exp, act = self.v_link_exp.get(), self.v_link_act.get()
        if not exp or not act:
            return
        cfgmod.set_model_link(exp, act)
        self._after_link_change()

    def _unlink_model(self):
        exp = self.v_link_exp.get()
        if exp:
            cfgmod.set_model_link(exp, "")
            self._after_link_change()

    def _after_link_change(self):
        if self.inv is not None:
            self.inv.mapping = cfgmod.model_map()
            self._set_inventory(self.inv, self._inv_error)      # statuses, tabs and the overlay follow at once
        self._status("Link saved.")

    # ---------- extra_model_paths.yaml ----------

    def _choose_yaml(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self._settings_win or self.root, title="ComfyUI's extra_model_paths.yaml",
                                          filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")])
        if path:
            self.settings_set_yaml(path)

    def settings_set_yaml(self, path: str):
        """Also the entry for a dropped file later (tkinterdnd2 is not part of this lane)."""
        cfgmod.set_extra_paths_file(str(path or ""))
        self._detect_async(reread=False)
