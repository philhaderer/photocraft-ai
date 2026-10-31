"""The download symbols of the settings window (14c step 5): one file, or "all missing" of a model.

The file goes into the sub-folder of its kind in ComfyUI's ``models`` folder (``comfydir.py`` finds it, the window asks once if it
cannot), after an OK that names file, size and target. Every file loads in its own thread, all at the same time (``downloads.py``);
progress, end and errors come back as "download" events. Files that need a login (gated) or come from another site open their page in the browser.
"""
from __future__ import annotations

import os
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from . import comfydir, downloads, manifest
from .gui_common import *  # noqa: F401,F403

DIRECT_HOSTS = ("huggingface.co", "githubusercontent.com")      # the plugin loads from these itself (Civitai: its page opens)


def browser_only(f) -> bool:
    """A file the plugin does not load itself: gated at Hugging Face (needs a login, the token panel comes later) or from Civitai."""
    return "gated" in f.note.lower() or not downloads._host_ok(f.url, DIRECT_HOSTS)


def site_hint(f) -> str:
    """The orange note of a file that cannot be loaded by the plugin: where to go and where to put it."""
    if "gated" in f.note.lower():
        return "Log in at Hugging Face and accept the licence. The disk symbol opens the page."
    host = urllib.parse.urlsplit(f.url).hostname or "the website"
    return f"The disk symbol opens {host} in your browser. Save the file in {f.target}."


def size_text(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


class DownloadMixin:
    # ---------- state ----------

    def _dl_init(self):
        self._dl: dict[str, dict] = {}              # file name -> {"file", "target", "done", "total", "phase", "cancel"} (running)
        self._dl_restart: set[str] = set()          # loaded, but ComfyUI does not list it yet
        self._dl_widgets: dict[str, dict] = {}      # file name -> the progress widgets of its row
        self._comfy_root: Path | None = None        # found for this session

    def _dl_info(self, name: str) -> dict | None:
        """For a row: None, or {"state": loading / verifying, "done", "total"}."""
        st = self._dl.get(name)
        if st is None:
            return None
        return {"state": "verifying" if st["phase"] == "verifying" else "loading", "done": st["done"], "total": st["total"]}

    # ---------- where the files go ----------

    def models_dir(self, ask: bool = True) -> Path | None:
        """ComfyUI's ``models`` folder: the test override (the "without models" test start uses a sandbox folder), the folder you chose once, the one of the running ComfyUI, else ask."""
        env = os.environ.get("PCCOMFY_MODELS_DIR")
        if not env and os.environ.get("PCCOMFY_SIMULATE_NO_MODELS"):      # the "ComfyUI without models" test start: a sandbox folder
            env = str(cfgmod.CONFIG_DIR / "test-downloads")                # noqa: F405
        if env:
            p = Path(env)
            p.mkdir(parents=True, exist_ok=True)
            return p
        saved = cfgmod.get_setting("comfy_models_dir")      # noqa: F405
        if saved and Path(saved).is_dir():
            return Path(saved)
        if self._comfy_root is None:
            self._comfy_root = comfydir.find_root(self.comfy.url) or Path("")
        found = comfydir.models_dir_of(self._comfy_root) if str(self._comfy_root) not in ("", ".") else None
        if found is not None:
            return found
        if not ask:
            return None
        from tkinter import filedialog
        chosen = filedialog.askdirectory(parent=self._settings_win or self.root, title="Where is your ComfyUI? Choose its folder "
                                         "(the one with main.py and models)")
        p = comfydir.models_dir_of(chosen) if chosen else None
        if chosen and p is None:
            self._status("There is no models folder in that folder.", error=True)
        if p is not None:
            cfgmod.set_setting("comfy_models_dir", str(p))      # noqa: F405
        return p

    # ---------- the buttons ----------

    def download_file(self, name: str):
        """The disk symbol of a file."""
        f = manifest.FILES.get(name)
        if f is None or not f.url or name in self._dl:
            return
        if browser_only(f):
            webbrowser.open(f.url)
            self._status(f"{name}: needs a login or comes from another site, so its page is open in your browser.")
            return
        base = self.models_dir()
        if base is None:
            return
        try:
            target = downloads.target_for(base, f)
        except downloads.DownloadError as e:
            self._status(str(e), error=True)
            return
        if target.exists():
            self._status(f"{name} is already in {target.parent}. Restart ComfyUI if it does not list it.")
            return
        if not messagebox.askokcancel("Download", f"Download {name}?\n\nSize: {f.size_text or 'unknown'}\nTo: {target}\n\n"        # noqa: F405
                                      "If it is interrupted, starting it again goes on where it stopped.",
                                      parent=self._settings_win or self.root):
            return
        self._dl_add([(f, target)])

    def download_missing(self, key, required_only: bool = False):
        """The disk symbol in a model's head: every file of it that is missing (all of them load at the same time). Files that
        need a website (gated, Civitai) are named in the OK window and their pages open in the browser. `key` may be several
        models (the Easy Mode tab: the starter models; a file two models share is listed once)."""
        if self.inv is None:
            return
        keys = (key,) if isinstance(key, str) else tuple(key)
        todo = []
        for row in (r for r in self.inv.rows() if r["key"] in keys):
            for f, found, lv in row["files"]:
                if found is None and f.url and f.name not in self._dl and f not in todo and (lv == "required" or not required_only):
                    todo.append(f)
        own = [f for f in todo if not browser_only(f)]
        site = [f for f in todo if browser_only(f)]
        if not own and not site:
            return
        pairs, base = [], None
        if own:
            base = self.models_dir()
            if base is None:
                return
            for f in own:
                try:
                    t = downloads.target_for(base, f)
                except downloads.DownloadError as e:
                    self._status(str(e), error=True)
                    return
                if not t.exists():
                    pairs.append((f, t))
        parts = []
        if pairs:
            names = "\n".join(f"  {f.name}  {f.size_text}" for f, _t in pairs)
            parts.append(f"Download {len(pairs)} file(s), {size_text(sum(f.size for f, _t in pairs))} in all?\n\n{names}\n\nTo: {base}")
        if site:
            parts.append("These need a website and open in your browser:\n" + "\n".join(f"  {f.name}  ({f.target})" for f in site))
        if not parts:
            self._status("The files are already in the folder. Restart ComfyUI if it does not list them.")
            return
        if not messagebox.askokcancel("Download", "\n\n".join(parts), parent=self._settings_win or self.root):         # noqa: F405
            return
        for f in site:
            webbrowser.open(f.url)
        if pairs:
            self._dl_add(pairs)

    def _dl_add(self, pairs):
        for f, target in pairs:
            self._dl[f.name] = {"file": f, "target": target, "done": 0, "total": f.size, "phase": "downloading", "cancel": threading.Event()}
            threading.Thread(target=self._dl_work, args=(f.name,), daemon=True).start()
        self._settings_fill()

    def download_cancel(self, name: str):
        """The cross of a row: stops it (what is loaded stays for a later resume)."""
        st = self._dl.get(name)
        if st is not None:
            st["cancel"].set()

    def _dl_work(self, name: str):
        put, st = self.events.put, self._dl.get(name)
        if st is None:
            return
        f, last = st["file"], [0.0]

        def progress(done, total, phase):
            now = time.monotonic()
            if now - last[0] >= 0.15 or done >= total:
                last[0] = now
                put(("download", ("progress", name, done, total, phase)))
        try:
            downloads.download(f.url, st["target"], size=f.size, sha256=f.sha256, progress=progress, cancel=st["cancel"].is_set)
            put(("download", ("end", name, "ok", "")))
        except downloads.Cancelled:
            put(("download", ("end", name, "cancelled", "")))
        except downloads.DownloadError as e:
            put(("download", ("end", name, "error", str(e))))
        except Exception as e:      # noqa: BLE001  (a worker must not die silently)
            put(("download", ("end", name, "error", f"Unexpected: {e}")))

    def _download_event(self, data):
        kind, name = data[0], data[1]
        st = self._dl.get(name)
        if st is None:
            return
        if kind == "progress":
            st["done"], st["total"], st["phase"] = data[2], data[3] or st["total"], data[4]
            self._dl_paint(name)
            return
        _k, _n, result, text = data
        self._dl.pop(name, None)
        if result == "ok":
            self._dl_restart.add(name)
            self._status(f"Loaded {name}. If ComfyUI does not list it, restart ComfyUI.")
            self.comfy.invalidate()
            self._detect_async()
        elif result == "cancelled":
            self._status(f"Cancelled: {name}. Loading it again goes on where it stopped.")
        else:
            self._status(f"{name}: {text}", error=True)
        self._settings_fill()

    def _dl_paint(self, name: str):
        w, info = self._dl_widgets.get(name), self._dl_info(name)
        if not w or not info:
            return
        total = info["total"]
        try:
            w["bar"].configure(maximum=max(total, 1), value=info["done"])
            pct = f"{round(100 * info['done'] / total)} %" if total else size_text(info["done"])
            w["label"].configure(text="checking" if info["state"] == "verifying" else pct)
        except (tk.TclError, KeyError):      # noqa: F405
            pass
