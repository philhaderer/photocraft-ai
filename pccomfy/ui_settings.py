"""Settings overlay, model detection in the window, greyed tabs (lane L1, PLAN.md tasks 6 to 8).

``SettingsMixin`` stands first in ``App``'s bases, so its methods wrap the ones of the other mixins (it calls ``super()``):

* ``refresh`` / ``_apply_refresh``: also read ComfyUI's installed files (in a thread, the result arrives as a "refresh" event);
* ``_update_mode_radios``: a mode whose files are missing is greyed out, its tooltip says what is missing;
* ``_on_model``: a click on a greyed tab opens the settings instead of switching to it;
* ``generate``: the preflight; a missing file stops the run with one clear line (file, folder, link).

The gear button next to the tabs opens the overlay: what is installed per tab, links to download, "link a file of another
name", and the credits. All decisions live in ``inventory.py`` and ``manifest.py`` (no Tk there).
"""
from __future__ import annotations

import difflib
import webbrowser

from . import icons, inventory, manifest, sthead
from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from .gui_theme import ICON_PX
from .ui_downloads import DownloadMixin, browser_only, site_hint, size_text

_LABELS = dict(MODE_LABELS)      # noqa: F405
EMPTY_TEXT = {"choose": "Choose a model", "none_linked": "Link your model in the settings"}
STATE_TEXT = {"ready": "ready", "partial": "some functions need files", "missing": "files missing"}
DOT_RED = "#e5484d"                   # the dot in front of a model that is not available (nothing in front of a ready one)
DOT_PAD = 4                            # px of room to the left of the dot (user 1.11.)
SETTINGS_W, SETTINGS_H = 760, 700      # the settings window at first (before the display scaling); then the size it was closed at
SET_ICON_PX = 16                       # the download and chain symbols next to a file
SET_STYLES = {"head": "SetHead.TLabel", "ok": "SetOk.TLabel", "bad": "SetBad.TLabel", "note": "SetNote.TLabel",
              "muted": "SetMuted.TLabel"}


def licence_of(note: str) -> str:
    """Only the licence part of a manifest note ("optional: sharper ...; licence: MIT (...)" -> "licence: MIT (...)")."""
    return next((p.strip() for p in note.split(";") if p.strip().startswith("licence")), note)


def file_path(f) -> str:
    """Where a file lies inside ComfyUI's models folder, as the window shows it: "/loras/Flux 3/flux-3-...safetensors"."""
    return "/" + f.folder + "/" + f.name.replace("\\", "/")
GEAR_PX = round(ICON_PX * 0.6)     # the gear: about 60 % of the other button icons, flat without a button background (user 28.10.)
FOOT_REFRESH_PADX, FOOT_RESET_PADX = (4, 0), (12, 0)     # footer: the refresh arrow close to the ComfyUI dot, "Reset page" apart


class SettingsMixin(DownloadMixin):
    inv = None                  # inventory.Inventory of the last successful reading (None = ComfyUI not read / not reachable)
    _inv_error = ""
    _settings_win = None
    _page_w: dict = {}          # the width of each settings tab (wrapping texts follow it)
    _settings_focus = None
    _last_model = ""
    _refreshing = False         # inside StateMixin._apply_refresh (its "open on the first model" step is not wanted here)
    _startup_checked = False    # the first reading after start has been looked at (a last model that is gone is let go once)
    _live_off_missing = False   # "Live preview" was switched off because the model's preview decoder is missing

    # ---------- build (one call at the end of App._build) ----------

    def _build_settings(self, foot):
        """The gear button at the right end of the footer row (the one with the connection dot, the refresh arrow and "Reset page")."""
        self._last_model = self.v_model.get()
        self._dl_init()
        self._page_w = {}
        self._map_start = cfgmod.model_map()       # the links at startup ("Reset to startup")
        self._map_undo: list[dict] = []            # the links before each change ("Undo")
        style = ttk.Style()
        style.configure("Missing.Tab.Toolbutton", foreground=NA_RED)      # a tab that is not available: red text, the background of an inactive tab
        self.b_gear = ttk.Button(foot, image=self._icon("gear", px=GEAR_PX), style="Link.TButton", command=self.toggle_settings)
        self.b_gear.pack(side="right")
        Tooltip(self.b_gear, "Settings: which model files ComfyUI has, links to get the missing ones, credits.")
        style.configure("Empty.TLabel", foreground=MUTED, font=font(11))
        self.v_empty = tk.StringVar(value="")
        self.lbl_empty = ttk.Label(self.root, textvariable=self.v_empty, style="Empty.TLabel", anchor="center", justify="center",
                                   wraplength=self._px(MIN_W - 40))
        self._foot_hidden = False
        self._apply_start_state(fit=False)

    # ---------- reading ComfyUI ----------

    def refresh(self):
        super().refresh()
        self._detect_async()

    def _detect_async(self):
        mapping, comfy = cfgmod.model_map(), self.comfy

        def work():
            res = {"_detect": True}
            try:
                res["_inv"], res["_inv_error"] = inventory.fetch(comfy, mapping), ""
            except ComfyError as e:
                res["_inv"], res["_inv_error"] = None, str(e)
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
        self._set_inventory(info["_inv"], info.get("_inv_error", ""))

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
            if st.detail:       # some functions lack files: the model is locked, the tooltip names each function
                return "\n".join(inventory.tooltip_text(s, _LABELS.get(mode, mode)) for mode, s in st.detail.items())
            return inventory.tooltip_text(st)
        if st.optional_missing:
            return "Not installed (optional): " + ", ".join(f.name for f in st.optional_missing[:3])
        return ""

    def _update_tabs(self):
        tts = getattr(self, "tt_tabs", {})
        hidden = cfgmod.hidden_tabs()
        for key, var in (getattr(self, "_shown_vars", None) or {}).items():    # the gear window follows the right-click menu
            var.set(key not in hidden)
        for m in models.MODELS:
            rb = self.rb_tabs.get(m.key)
            if rb is None:
                continue
            st = self.inv.tab_status(m.key) if self.inv is not None else None
            rb.configure(style="Missing.Chip.Toolbutton" if not self._model_usable(m.key, self.v_mode.get()) else "Chip.Toolbutton")
            tt = tts.get(m.key)
            if tt is not None:
                extra = self._tab_extra(st) if st is not None else ""
                tt.text = m.tip + (("\n\n" + extra) if extra else "")

    def _model_usable(self, key: str, mode: str) -> bool:
        """Has ComfyUI the files this model needs? The whole model counts, not only the chosen function: a model with one
        function lacking its files is locked (user 30.10.), so nothing is offered that was not tested with its standard settings."""
        if self.inv is None:
            return True
        return self.inv.tab_status(key).state != "missing"

    def _update_mode_radios(self):
        super()._update_mode_radios()
        self._update_tabs()                 # a model chip turns red when its files for the chosen function are missing
        self._update_live_preview()
        self._update_llm_button()
        self._enforce_switch_files()
        m = self._model()
        if m is None or self.inv is None:
            return
        for key in m.modes:                 # the function stays clickable; its tooltip says what the chosen model misses for it
            s = self.inv.mode_status(m.key, key)
            if s.state == "missing":
                self.tt_modes[key].text += "\n\n" + inventory.tooltip_text(s, _LABELS.get(key, key))

    def _update_live_preview(self):
        """ "Live preview" needs the model's preview decoder: while it is missing the switch is off and cannot be clicked
        (user 30.10.); once the file is there it is on again, as at every start."""
        m = self._model()
        dec = manifest.preview_decoder(m.key) if m is not None else ""
        missing = bool(dec) and self.inv is not None and self.inv.found(dec) is None
        cb = getattr(self, "cb_live", None)
        if cb is None:
            return
        if missing:
            if not self._live_off_missing:
                self._live_off_missing = True
                self.v_live.set(False)
            cb.configure(state="disabled")
            self.tt_live.text = LIVE_TIP + f"\n\nNeeds {dec}: download it in the settings (gear), under Additional models."
        else:
            if self._live_off_missing:
                self._live_off_missing = False
                self.v_live.set(True)
            cb.configure(state="normal")
            self.tt_live.text = LIVE_TIP

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
        if getattr(self, "_minimized", False):      # minimised: only the header stays (gui.py toggle_minimize)
            if fit and getattr(self, "_sized", False):
                self._fit_height()
            return
        below = self.f_preview if self.f_preview.winfo_manager() else self.f_status   # the live preview sits above the status line:
        if state != "none_linked":                                                     # the tabs must not slip under it
            self.f_tabs.pack(fill="x", padx=10, pady=(8, 2), before=below)
        if state:
            self.lbl_empty.pack(fill="x", padx=10, pady=(26, 22), before=below)
        else:
            self.f_scrollbox.pack(fill="x", before=below)     # the body sits in its scroll box (gui.py)
        hide_foot = state == "none_linked"
        if hide_foot != self._foot_hidden:
            self._foot_hidden = hide_foot
            for w in (self.lbl_conn, self.b_refresh, self.b_reset):
                w.pack_forget()
            if not hide_foot:
                self.lbl_conn.pack(side="left")
                self.b_refresh.pack(side="left", padx=FOOT_REFRESH_PADX)
                self.b_reset.pack(side="left", padx=FOOT_RESET_PADX)
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

    def _settings_rows(self) -> list[tuple]:
        """The "Models" tab as rows (kind, data), drawn by _settings_draw; no Tk here. Kinds: "error" (text, detail), "intro"
        (text), "model" (key, label, state, focus), "file" (a dict, see below), "node" (class, pack, url), "head" (text),
        "line" (text, style). A file row: expected name, path with its folder ("/vae/flux2-vae.safetensors"), found (your
        file's name or None), level (required / optional), size text, download url, note, found on disk (a path or "")."""
        rows: list[tuple] = []
        links = cfgmod.model_map()
        rows.append(("links", "Linked files"))
        info = "Use your own file instead of an expected one. Click the chain symbol next to a file and pick yours."
        if self.inv is not None:                 # one paragraph (user 31.10.)
            info += (" ComfyUI reads its model folders only when it starts: after copying a file, restart ComfyUI "
                     "and click the refresh arrow (⟳) at the bottom of the plugin.")
        info += (" A model is offered in the plugin only when the files for its standard settings are there; a function whose "
                 "standard settings need a missing file is greyed out.")
        rows.append(("intro", info))
        rows += [("line", f"{k}  →  {v}", "muted") for k, v in sorted(links.items())]
        if self.inv is None:
            rows.append(("error", "ComfyUI could not be read.", (self._inv_error or "Not connected yet.")
                         + "\nStart ComfyUI, then click the refresh arrow (⟳) at the bottom of the plugin."))
            rows += [("enable", m.key, m.label, True) for m in models.MODELS]
        else:
            for row in self.inv.rows():
                miss = [f for f, found, lv in row["files"] if found is None and f.url and lv == "required"]
                direct = [f for f in miss if not browser_only(f)]
                rows.append(("model", row["key"], row["label"], row["status"].state, row["key"] == self._settings_focus,
                             {"count": len(direct), "site": len(miss) - len(direct), "size": size_text(sum(f.size for f in direct))}
                             if miss else None))
                rows.append(("enable", row["key"], row["label"], row["status"].state != "missing"))
                rows.append(("sep",))
                rows.append(("modes", row["key"], self._mode_cover(row["key"])))
                rows.append(("line", manifest.describe_line(row["key"], self.inv.has), "muted"))
                rows.append(("sep",))
                rows.append(("head", "Needs these weights:"))
                for f, found, level in row["files"]:
                    rows.append(("file", self._file_data(f, found, level)))
                for c in row["status"].nodes:
                    pack = manifest.node_pack(c)
                    rows.append(("node", c, pack[0] if pack else "", pack[1] if pack else ""))
            rows.append(("head", "Additional models (used by several models)"))
            for f, found, use, keys in self.inv.additional_rows():
                rows.append(("file", {**self._file_data(f, found, "optional"),
                                      "use": f"{use}: " + ", ".join(models.SHORT[k] for k in keys),
                                      "note": licence_of(f.note) if found is None else ""}))
        return rows

    def _mode_cover(self, key: str) -> list[tuple]:
        """The functions a model covers: (mode key, label, state, tooltip); state ready / missing (a file or node is missing) /
        none (the model does not offer it)."""
        m = models.BY_KEY[key]
        out = []
        for mode, label in MODE_LABELS:           # noqa: F405
            if mode == "img2img":
                continue
            if mode not in m.modes:
                out.append((mode, label, "none", "This model does not offer this function."))
                continue
            st = self.inv.mode_status(key, mode) if self.inv is not None else None
            if st is None or st.state == "ready":
                out.append((mode, label, "ready", "Ready."))
            else:
                need = [f.name for f in st.missing] + list(st.nodes)
                out.append((mode, label, "missing", "Missing: " + ", ".join(need[:3]) + (" ..." if len(need) > 3 else "")))
        return out

    def _file_data(self, f, found, level) -> dict:
        """One file row: expected name, path, found (your file's name or None), level, size, url, note, the download state
        (see DownloadMixin._dl_info), "restart" (loaded, ComfyUI does not list it yet) and "browser" (its page opens instead)."""
        return {"name": f.name, "path": file_path(f), "found": found, "level": level, "size": f.size_text, "url": f.url,
                "note": f.note if found is None else "", "dl": self._dl_info(f.name),
                "restart": found is None and f.name in self._dl_restart, "browser": browser_only(f) if f.url else False,
                "hint": site_hint(f) if (found is None and f.url and browser_only(f)) else ""}

    def _credits_segments(self) -> list[tuple]:
        """The "Credits" tab: who made the code, nodes and models the plugin builds on (links)."""
        seg: list[tuple] = []
        add = lambda text, style="", url="": seg.append((text, style, url))  # noqa: E731
        add("Credits\n", "head")
        for name, what, url in manifest.CONTRIBUTORS:
            add("    ", "")
            add(name, "link", url)
            add(f"  {what}\n", "muted")
        return seg

    def _link_candidates(self, expected: str) -> list[str]:
        """The files ComfyUI lists for the kind of ``expected`` that can stand in for it (itself left out), the ones with a
        name most like it first. ComfyUI's own list: it knows its folders, the default one, the extra ones and links."""
        f = manifest.FILES.get(expected)
        if f is None or self.inv is None:
            return []
        avail = list(self.inv.lists.get(f.kind, []))
        own = inventory.resolve(f.name, avail, None, f.aliases)
        base = lambda n: n.replace("\\", "/").rpartition("/")[2].lower()      # noqa: E731
        return sorted((n for n in avail if n != own),
                      key=lambda n: -difflib.SequenceMatcher(None, base(n), base(f.name)).ratio())

    def _link_hints(self, expected: str, cands: list[str]) -> dict[str, str]:
        """For the files of the chain list: "looks like <file>" when the file's size and its safetensors header match a file of
        the manifest (a renamed copy; for the expected file itself it reads "looks like <expected>"), "incomplete?" when the header promises
        more bytes than the file has. Only for files in ComfyUI's models folder (the ones in extra folders have no hint)."""
        f = manifest.FILES.get(expected)
        base = self.models_dir(ask=False) if f is not None else None
        if base is None:
            return {}
        by_size = {g.size: g.name for g in manifest.FILES.values() if g.kind == f.kind and g.size}
        out: dict[str, str] = {}
        for n in cands:
            p = base / f.folder / n.replace("\\", "/")
            try:
                size = p.stat().st_size
            except OSError:
                continue
            head = sthead.read_header(p)
            if head is None:
                continue
            if not sthead.is_complete(p):
                out[n] = "incomplete?"
            elif size in by_size:
                out[n] = "looks like " + by_size[size]
        return out

    # ---------- the overlay window ----------

    def toggle_settings(self):
        """The gear: opens the settings window, or closes it when it is open (user 28.10.)."""
        win = self._settings_win
        if win is not None:
            try:
                alive = bool(win.winfo_exists())
            except tk.TclError:
                alive = False
            if alive:
                self._settings_close()
                return
            self._settings_win = None
        self.open_settings()

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
            win.minsize(self._px(480), self._px(300))      # narrower than this the model tabs would be cut off
            x = self.root.winfo_rootx() + self.root.winfo_width() + 8
            w, h = self._settings_size()
            win.geometry(f"{w}x{h}+{x}+{self.root.winfo_rooty()}")
        except (tk.TclError, TypeError):
            pass
        win.protocol("WM_DELETE_WINDOW", self._settings_close)
        self._settings_win = win
        self._own_settings(win)

        # no ComfyUI dot and no Refresh here: the plugin's footer has both

        nb = ttk.Notebook(win)              # tab 1: the models; tab 2: credits
        nb.pack(fill="both", expand=True, padx=10, pady=8)
        tab_models, tab_other, tab_credits = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(tab_models, text="All supported models")
        nb.add(tab_other, text="Other settings")      # general switches (user 1.11.): for now the tip popup
        nb.add(tab_credits, text="Credits")
        self._tips_setting_row(tab_other)
        self.nb_settings = nb

        # which models the plugin shows (user 29.10.): after installing, all are shown; untick to hide one (the right-click
        # menu of a chip hides too, only here a model comes back). The tick sits in the tab of its model (user 31.10.)
        hidden = cfgmod.hidden_tabs()
        self._shown_vars = {m.key: tk.BooleanVar(value=m.key not in hidden) for m in models.MODELS}

        # on top of "Models": the linked files (they hold for every model), below them one tab per model and "Additional"
        self.f_set_top = ttk.Frame(tab_models)
        self.f_set_top.pack(fill="x", side="top")
        self.f_set_top.bind("<Configure>", lambda e: self._settings_wrap("top", e.width), add="+")
        self.nb_models = ttk.Notebook(tab_models, style="Inner.TNotebook")
        self.nb_models.pack(fill="both", expand=True, pady=(6, 0))
        self._set_pages = {m.key: self._scroll_page(m.key, models.SHORT[m.key]) for m in models.MODELS}
        self._set_pages["additional"] = self._scroll_page("additional", "Additional")
        win.bind("<MouseWheel>", self._settings_wheel, add="+")      # only this window: the plugin's body has its own
        self._set_widgets = []

        self.t_credits = self._settings_text(tab_credits)
        self._settings_fill()
        if focus in self._set_pages:
            self._select_model_tab(focus)
        self._detect_async()       # a model copied in since the last reading is listed when the window opens (if ComfyUI sees it)

    def _scroll_page(self, key: str, title: str) -> dict:
        """One tab of the model notebook: a canvas that scrolls, its rows in a frame (the rows: one per file, in a frame each)."""
        box = ttk.Frame(self.nb_models)
        self.nb_models.add(box, text=title)
        cv = tk.Canvas(box, bg=BG, highlightthickness=0, bd=0)
        cv.pack(side="left", fill="both", expand=True)
        sb = ThinScrollbar(box, cv, self._px(6), BG, auto=True)
        rows = ttk.Frame(cv)
        win_id = cv.create_window(0, 0, window=rows, anchor="nw")
        cv.bind("<Configure>", lambda e: (cv.itemconfigure(win_id, width=e.width), self._settings_wrap(key, e.width)), add="+")
        rows.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")), add="+")
        return {"page": box, "cv": cv, "sb": sb, "rows": rows}

    def _settings_wheel(self, e):
        """The mouse wheel scrolls the model tab that is open."""
        try:
            key = list(self._set_pages)[self.nb_models.index(self.nb_models.select())]
        except (tk.TclError, TypeError, IndexError, AttributeError):
            return
        self._set_pages[key]["sb"].wheel(e)

    def _select_model_tab(self, key: str):
        try:
            self.nb_models.select(self._set_pages[key]["page"])
        except (tk.TclError, KeyError, AttributeError):
            pass

    def _settings_size(self) -> tuple[int, int]:
        """The window's size: the one it had when it was last closed, else about 760 x 700 (user 30.10.: wider, remembered)."""
        saved = cfgmod.get_setting("settings_size")
        if isinstance(saved, list) and len(saved) == 2 and all(isinstance(v, int) and v >= 300 for v in saved):
            return saved[0], saved[1]
        return self._px(SETTINGS_W), self._px(SETTINGS_H)

    def _settings_text(self, parent):
        body = ttk.Frame(parent)
        body.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(body)
        sb.pack(side="right", fill="y")
        t = tk.Text(body, wrap="word", bg=PANEL, fg=FG, relief="flat", borderwidth=0, padx=8, pady=6,
                    font=font(10), yscrollcommand=sb.set, cursor="arrow")
        t.pack(side="left", fill="both", expand=True)
        sb.configure(command=t.yview)
        return t

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
            w, h = win.winfo_width(), win.winfo_height()
            if isinstance(w, int) and isinstance(h, int) and w >= 300 and h >= 300 and [w, h] != cfgmod.get_setting("settings_size"):
                cfgmod.set_setting("settings_size", [w, h])      # the size you gave it comes back next time (user 30.10.)
        except (tk.TclError, AttributeError):
            pass
        try:
            win.destroy()
        except (tk.TclError, AttributeError):
            pass

    def _settings_fill(self):
        self._settings_draw(self._settings_rows())
        t_credits = getattr(self, "t_credits", None)
        if t_credits is not None:
            self._fill_text(t_credits, self._credits_segments())

    def _settings_sections(self, rows):
        """The flat rows split for the tabs: (the rows above the models, {model key: its rows}, the rows of "Additional")."""
        top, per, extra, cur = [], {}, [], None
        for row in rows:
            if row[0] in ("model", "enable") and row[1] != cur:
                cur = row[1]
                per[cur] = []
            elif row[0] == "head" and row[1].startswith("Additional"):
                cur = "additional"
            if cur is None:
                top.append(row)
            elif cur == "additional":
                extra.append(row)
            else:
                per[cur].append(row)
        return top, per, extra

    def _settings_draw(self, rows):
        """The rows of _settings_rows as widgets: the linked files on top, the rest in the tab of its model (or "Additional")."""
        for w in getattr(self, "_set_widgets", []):
            try:
                w.destroy()
            except (tk.TclError, AttributeError):
                pass
        self._set_widgets = []
        self._wrap_labels = []
        self._dl_widgets = {}
        top_frame, pages = getattr(self, "f_set_top", None), getattr(self, "_set_pages", None)
        if top_frame is None or pages is None:
            return
        top, per, extra = self._settings_sections(rows)
        self._draw_rows(top, top_frame, "top")
        for key, page in pages.items():
            self._draw_rows(extra if key == "additional" else per.get(key, []), page["rows"], key)
        self._settings_titles()
        self._settings_wrap()

    def state_dot(self, state: str):
        """The red dot in front of a model that is not active or available (some or all of its files are missing), with
        DOT_PAD px of room on its left; "" for a ready model (no mark)."""
        if state not in ("partial", "missing"):
            return ""
        cache = self.__dict__.setdefault("_icon_cache", {})
        if ("dot", state) not in cache:
            from PIL import Image, ImageDraw
            sc, d, pad = 4, self._px(9), self._px(DOT_PAD)
            im = Image.new("RGBA", ((d + pad) * sc, d * sc), (0, 0, 0, 0))
            ImageDraw.Draw(im).ellipse([pad * sc, 0, (pad + d) * sc - 1, d * sc - 1], fill=DOT_RED)
            cache[("dot", state)] = icons.photo(self.root, None, DOT_RED, d, image=im.resize((d + pad, d), Image.LANCZOS))
        return cache[("dot", state)]

    def _settings_titles(self):
        """The tab of a model carries its state: a red dot in front of the name when it is not available, nothing when ready."""
        for key, page in getattr(self, "_set_pages", {}).items():
            if key == "additional":
                continue
            st = self.inv.tab_status(key).state if self.inv is not None else ""
            try:
                self.nb_models.tab(page["page"], text=models.SHORT[key], image=self.state_dot(st), compound="left")
            except (tk.TclError, AttributeError):
                pass

    def _draw_rows(self, rows, parent, page: str):
        """One frame per row in ``parent``: a model's head line, then its files (mark and path on the left, size and the
        download and chain symbols packed at the right edge first, so a narrow window shortens or wraps the path and never
        lets the symbols cover it)."""
        made, count = self._set_widgets, [0]
        parent.columnconfigure(0, weight=1)
        slot = self._px(24)

        def line():
            f = ttk.Frame(parent)
            f.grid(row=count[0], column=0, sticky="ew")
            count[0] += 1
            made.append(f)
            return f

        def label(box, text, style, side="left", padx=(0, 0), pady=(0, 0), wrap=0, **kw):
            lb = ttk.Label(box, text=text, style=SET_STYLES.get(style, "SetText.TLabel"), **kw)
            lb.pack(side=side, padx=padx, pady=pady)
            if wrap:                                    # follows the width of the tab (see _settings_wrap)
                lb.configure(justify="left")
                self._wrap_labels.append((lb, wrap, page))
            return lb

        def icon(box, kind, tip, command, menu=None):
            b = ttk.Button(box, image=self._icon(kind, px=SET_ICON_PX), style="Link.TButton", command=command)
            b.pack(side="right", padx=(4, 0))
            Tooltip(b, tip)
            if menu is not None:
                b.bind("<Button-3>", menu, add="+")

        for row in rows:
            kind = row[0]
            if kind == "error":
                box = line()
                label(box, row[1], "bad", padx=(0, 0))
                box = line()
                label(box, row[2], "muted", pady=(0, 8), wrap=self._px(20))
            elif kind == "intro":
                label(line(), row[1], "muted", pady=(0, 4), wrap=self._px(20))
            elif kind == "model":
                _k, key, name, state, focus, allm = row
                box = line()
                if allm:
                    b = ttk.Button(box, text="Download all needed models", image=self._icon("save", px=SET_ICON_PX), compound="left",
                                   style="SetSmall.TButton", command=lambda k=key: self.download_missing(k, required_only=True))
                    b.pack(side="right", padx=(4, 0), pady=(6, 2))
                    Tooltip(b, f"Download the missing files this model needs ({allm['count']}, {allm['size']})"
                               + (f"; {allm['site']} open their page in the browser." if allm["site"] else "."))
                dot = self.state_dot(state)
                if dot:
                    ttk.Label(box, image=dot).pack(side="left", pady=(6, 2))
                label(box, name + "   " + STATE_TEXT[state] + ("   \u25C0" if focus else ""), "head", padx=(4 if dot else 0, 0), pady=(6, 2))
            elif kind == "enable":
                key = row[1]
                usable = row[3] if len(row) > 3 else True
                var = self._shown_vars[key]
                var.set(key not in cfgmod.hidden_tabs() if usable else False)     # a model without its files is not in the plugin
                cb = ttk.Checkbutton(line(), text="Show this model in the plugin", variable=var, style="SetText.TCheckbutton",
                                     command=lambda k=key, v=var: self._set_model_hidden(k, not v.get()))
                cb.pack(side="left", pady=(0, 4))
                made.append(cb)
                if usable:
                    Tooltip(cb, "Untick to hide this model in the plugin, tick to show it again.")
                else:
                    cb.configure(state="disabled")
                    Tooltip(cb, "This model can be shown only when the files for its standard settings are there (see below).")
                    label(line(), "Not offered in the plugin yet: the files for its standard settings are missing (✗ below). "
                                  "Get them, restart ComfyUI and click the refresh arrow.", "note", padx=(8, 0), pady=(0, 4), wrap=self._px(60))
            elif kind == "modes":
                label(line(), "Covers these modes:", "head", pady=(4, 2))
                grid = ttk.Frame(line())
                grid.pack(fill="x")
                made.append(grid)
                for i, (_mode, text, state, tip) in enumerate(m for m in row[2] if m[2] != "none"):     # a list: what the model offers
                    ttk.Label(grid, text="✗" if state == "missing" else "", width=2, style=SET_STYLES["ok"]).grid(
                        row=i, column=0, sticky="w", padx=(8, 0), pady=1)       # the one icon: an X on a mode with missing files
                    lb = ttk.Label(grid, text=text, style=SET_STYLES["ok"])
                    lb.grid(row=i, column=1, sticky="w", padx=(4, 0), pady=1)
                    Tooltip(lb, tip)
            elif kind == "file":
                f = row[1]
                ok = f["found"] is not None
                box = line()
                # the symbols first: pack gives the space to what is packed first, the path takes what is left
                icon(box, "link", "Use another file of yours for this one: opens the list of the files ComfyUI has.",
                     lambda n=f["name"]: self._choose_for(n))
                dl = f["dl"]
                if dl:                                  # loading: a bar and a cross instead of size and disk symbol
                    cancel = ttk.Button(box, text="\u2715", style="Link.TButton", width=2,
                                        command=lambda n=f["name"]: self.download_cancel(n))
                    cancel.pack(side="right", padx=(4, 0))
                    Tooltip(cancel, "Stop this download. What is loaded stays, loading it again goes on where it stopped.")
                    lb = ttk.Label(box, text="", style=SET_STYLES["muted"], width=8, anchor="e")
                    lb.pack(side="right")
                    bar = ttk.Progressbar(box, length=self._px(90), maximum=max(dl["total"], 1), value=dl["done"])
                    bar.pack(side="right", padx=(8, 4))
                    self._dl_widgets[f["name"]] = {"bar": bar, "label": lb}
                    self._dl_paint(f["name"])
                else:
                    if f["url"] and not ok:
                        tip = ("Opens the page in your browser (needs a login or comes from another site). Right-click: copy the link."
                               if f["browser"] else f"Download ({f['size'] or 'size unknown'}). Right-click: copy the download link.")
                        icon(box, "save", tip, lambda n=f["name"]: self.download_file(n), menu=lambda e, u=f["url"]: self._link_menu(e, u))
                    else:
                        ttk.Frame(box, width=slot, height=1).pack(side="right", padx=(4, 0))
                    lb = ttk.Label(box, text=f["size"] if (f["size"] and not ok) else "", style=SET_STYLES["muted"], width=8, anchor="e")
                    lb.pack(side="right")
                label(box, "\u2713" if ok else "\u2717", "ok" if ok else ("bad" if f["level"] == "required" else "note"), padx=(8, 6))
                label(box, f["path"] + ("   (optional, not used in standard settings)" if f["level"] == "optional" and not f.get("use") else ""),
                      "muted" if ok else "", wrap=self._px(130))
                extra = [(f["use"], "muted")] if f.get("use") else []
                if f["hint"]:
                    extra.append((f["hint"], "note"))               # orange: a website is needed
                if ok and f["found"] != f["name"]:
                    extra.append((f"your file: {f['found']}", "muted"))
                if f["restart"]:
                    extra.append(("loaded: restart ComfyUI and click the refresh arrow to list it", "note"))
                if f["note"] and not (f["hint"] and f["note"].lower().startswith("gated")):
                    extra.append((f["note"], "muted"))
                for text, style in extra:
                    label(line(), text, style, padx=(36, 0), wrap=self._px(60))
            elif kind == "node":
                _k, cls, pack, url = row
                box = line()
                if url:
                    icon(box, "link", f"Get {pack or 'the node pack'}: opens its page.", lambda u=url: webbrowser.open(u))
                label(box, "\u2717", "bad", padx=(8, 6))
                label(box, f"node {cls}" + (f"   \u2192 {pack}" if pack else ""), "", wrap=self._px(120))
            elif kind == "head":
                label(line(), row[1], "head", pady=(10, 2))
            elif kind == "sep":          # a light line before "Covers these modes" and "Needs these weights" (user 1.11.)
                ttk.Frame(line(), style="Sep.TFrame", height=1).pack(fill="x", pady=(8, 0))
            elif kind == "links":          # the head of "Linked files" with its Undo and Reset
                box = line()
                self.b_link_reset = ttk.Button(box, text="Reset to startup", command=self._link_reset, style="SetSmall.TButton")
                self.b_link_reset.pack(side="right", pady=(2, 2))
                Tooltip(self.b_link_reset, "All links as they were when the plugin started.")
                self.b_link_undo = ttk.Button(box, text="Undo", command=self._link_undo, style="SetSmall.TButton")
                self.b_link_undo.pack(side="right", padx=(0, 6), pady=(2, 2))
                Tooltip(self.b_link_undo, "Takes back the last change of the links.")
                label(box, row[1], "head", pady=(2, 2))
                self._link_buttons()
            elif kind == "line":
                label(line(), row[1], row[2], padx=(8, 0), wrap=self._px(40))

    def _settings_wrap(self, page: str | None = None, width: int | None = None):
        """Wrapping labels follow their tab: the width of the tab minus what stands beside them."""
        if page is not None and isinstance(width, int):
            self._page_w[page] = width
        for lb, margin, pg in getattr(self, "_wrap_labels", []):
            if page is not None and pg != page:
                continue
            w = self._page_w.get(pg)
            if not isinstance(w, int) or w < 50:
                w = self._px(SETTINGS_W - 40)
            try:
                lb.configure(wraplength=max(self._px(120), w - margin))
            except tk.TclError:
                pass

    def _link_menu(self, e, url: str):
        """Right-click on a download symbol: copy its link (user 30.10.)."""
        menu = tk.Menu(self._settings_win or self.root, tearoff=0)
        menu.add_command(label="Copy download link", command=lambda: self._copy_text(url, "Download link copied."))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _copy_text(self, text: str, msg: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._status(msg)

    def _fill_text(self, t, segments):
        try:
            top = t.yview()[0]
        except (tk.TclError, TypeError, IndexError):
            top = 0.0
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.tag_configure("head", font=font(10, bold=True), foreground=FG)
        t.tag_configure("ok", foreground=DONE_GREEN)           # noqa: F405
        t.tag_configure("bad", foreground=ERROR_TEXT)          # noqa: F405
        t.tag_configure("note", foreground="#ffffff")
        t.tag_configure("muted", foreground=MUTED)
        n = 0
        for text, style, url in segments:
            tags = (style,) if style and style != "link" else ()
            if style in ("link", "pick"):
                n += 1
                tag = f"link{n}"
                t.tag_configure(tag, foreground=ACCENT_TEXT, underline=True)
                if style == "pick":
                    t.tag_bind(tag, "<Button-1>", lambda e, u=url: self._choose_for(u))
                else:
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

    # ---------- link a file of another name ----------

    def _link_buttons(self):
        try:
            self.b_link_undo.configure(state="normal" if self._map_undo else "disabled")
            self.b_link_reset.configure(state="normal" if cfgmod.model_map() != self._map_start else "disabled")
        except (AttributeError, tk.TclError):
            pass

    def _choose_for(self, expected: str):
        """The chain next to a file: a list of the files ComfyUI has for its kind, the most similar first, "Unlink" last when
        the file is linked. A click links at once (Undo and Reset are in "Linked files")."""
        cands, mapped = self._link_candidates(expected), cfgmod.model_map().get(expected)
        if not cands and not mapped:
            self._status("ComfyUI lists no other file of this kind. Copy yours into its folder and restart ComfyUI.", error=True)
            return
        hints = self._link_hints(expected, cands)
        cands = sorted(cands, key=lambda n: not hints.get(n, "").startswith("looks like " + expected))   # a match of the expected file first (sort is stable)
        menu = tk.Menu(self._settings_win or self.root, tearoff=0)
        for n in cands:
            tag = f"   ({hints[n]})" if n in hints else ""
            menu.add_command(label=("✓ " if n == mapped else "") + n + tag, command=lambda n=n: self._link_models(expected, n))
        if mapped:
            if cands:
                menu.add_separator()
            menu.add_command(label="Unlink (use the expected file again)", command=lambda: self._link_models(expected, ""))
        win = self._settings_win or self.root
        try:
            menu.tk_popup(win.winfo_pointerx(), win.winfo_pointery())
        finally:
            menu.grab_release()

    def _link_models(self, expected: str, actual: str):
        """The plugin uses ``actual`` from now on for ``expected`` ("" removes the link)."""
        before = cfgmod.model_map()
        cfgmod.set_model_link(expected, actual)
        if cfgmod.model_map() != before:
            self._map_undo.append(before)
        self._after_link_change("Linked: " + (f"{expected} → {actual}." if actual else f"{expected} is used again."))

    def _link_undo(self):
        if self._map_undo:
            cfgmod.set_model_map(self._map_undo.pop())
            self._after_link_change("Undone: the links are as before the last change.")

    def _link_reset(self):
        if cfgmod.model_map() != self._map_start:
            self._map_undo.clear()           # Undo takes back relinks only, not the reset (user, 27.10.)
            cfgmod.set_model_map(dict(self._map_start))
            self._after_link_change("The links are as they were at startup.")

    def _after_link_change(self, msg: str = "Link saved."):
        if self.inv is not None:
            self.inv.mapping = cfgmod.model_map()
            self._set_inventory(self.inv, self._inv_error)      # statuses, tabs and the overlay follow at once
        self._status(msg)
