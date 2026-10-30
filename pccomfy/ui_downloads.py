"""The download symbols of the settings window (14c step 5): one file, or "all missing" of a model.

The file goes into the sub-folder of its kind in ComfyUI's ``models`` folder (``comfydir.py`` finds it, the window asks once if it
cannot), after an OK that names file, size and target. The loading runs in one worker thread (``downloads.py``); progress, end and
errors come back as "download" events. Files that need a login (gated) or come from another site open their page in the browser.
"""
from __future__ import annotations

import os
import threading
import time
import webbrowser
from pathlib import Path

from . import comfydir, downloads, manifest
from .gui_common import *  # noqa: F401,F403

DIRECT_HOSTS = ("huggingface.co", "github.com")      # the plugin loads from these itself (Civitai: its page opens)


def browser_only(f) -> bool:
    """A file the plugin does not load itself: gated at Hugging Face (needs a login, the token panel comes later) or from Civitai."""
    return "gated" in f.note.lower() or not downloads._host_ok(f.url, DIRECT_HOSTS)


def size_text(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


class DownloadMixin:
    # ---------- state ----------

    def _dl_init(self):
        self._dl: dict[str, dict] = {}              # file name -> {"file", "target", "done", "total", "phase", "cancel"} (queued and running)
        self._dl_order: list[str] = []              # the queue, the running one first
        self._dl_restart: set[str] = set()          # loaded, but ComfyUI does not list it yet
        self._dl_widgets: dict[str, dict] = {}      # file name -> the progress widgets of its row
        self._dl_thread = None
        self._dl_lock = threading.Lock()
        self._comfy_root: Path | None = None        # found for this session

    def _dl_info(self, name: str) -> dict | None:
        """For a row: None, or {"state": queued / loading / verifying, "done", "total"}."""
        st = self._dl.get(name)
        if st is None:
            return None
        if name not in self._dl_order[:1]:
            return {"state": "queued", "done": 0, "total": 0}
        return {"state": "verifying" if st["phase"] == "verifying" else "loading", "done": st["done"], "total": st["total"]}

    # ---------- where the files go ----------

    def models_dir(self, ask: bool = True) -> Path | None:
        """ComfyUI's ``models`` folder: the test override, the folder you chose once, the one of the running ComfyUI, else ask."""
        env = os.environ.get("PCCOMFY_MODELS_DIR")
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

    def download_missing(self, key: str):
        """The disk symbol in a model's head: every file of it that is missing."""
        if self.inv is None:
            return
        row = next((r for r in self.inv.rows() if r["key"] == key), None)
        todo = [f for f, found, _lv in (row["files"] if row else []) if found is None and f.url and f.name not in self._dl]
        own = [f for f in todo if not browser_only(f)]
        if not own:
            self._status("Nothing to load here: the missing files need a login or come from another site (use their own symbol).")
            return
        base = self.models_dir()
        if base is None:
            return
        pairs = []
        for f in own:
            try:
                t = downloads.target_for(base, f)
            except downloads.DownloadError as e:
                self._status(str(e), error=True)
                return
            if not t.exists():
                pairs.append((f, t))
        if not pairs:
            self._status("The files are already in the folder. Restart ComfyUI if it does not list them.")
            return
        total = sum(f.size for f, _t in pairs)
        names = "\n".join(f"  {f.name}  {f.size_text}" for f, _t in pairs)
        if not messagebox.askokcancel("Download", f"Download {len(pairs)} file(s), {size_text(total)} in all?\n\n{names}\n\n"       # noqa: F405
                                      f"To: {base}",
                                      parent=self._settings_win or self.root):
            return
        self._dl_add(pairs)

    def _dl_add(self, pairs):
        for f, target in pairs:
            self._dl[f.name] = {"file": f, "target": target, "done": 0, "total": f.size, "phase": "downloading", "cancel": threading.Event()}
            self._dl_order.append(f.name)
        self._dl_pump()
        self._settings_fill()

    def download_cancel(self, name: str):
        """The cross of a row: stops the running one (its loaded part stays for a later resume) or takes a queued one out."""
        st = self._dl.get(name)
        if st is None:
            return
        st["cancel"].set()
        if name not in self._dl_order[:1]:          # not started: gone at once
            self._dl.pop(name, None)
            self._dl_order = [n for n in self._dl_order if n != name]
            self._settings_fill()

    # ---------- the worker ----------

    def _dl_pump(self):
        with self._dl_lock:
            if self._dl_thread is not None:
                return
            self._dl_thread = threading.Thread(target=self._dl_work, daemon=True)
            self._dl_thread.start()

    def _dl_work(self):
        put = self.events.put
        while True:
            with self._dl_lock:
                name = next((n for n in list(self._dl_order) if n in self._dl and not self._dl[n]["cancel"].is_set()), None)
                if name is None:
                    self._dl_thread = None
                    return
            st = self._dl.get(name)
            if st is None:
                continue
            f, last = st["file"], [0.0]

            def progress(done, total, phase, name=name, last=last):
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
            while name in self._dl_order and name in self._dl:      # wait until the window took the end (keeps the order right)
                time.sleep(0.05)

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
        self._dl_order = [n for n in self._dl_order if n != name]
        if result == "ok":
            self._dl_restart.add(name)
            self._status(f"Loaded {name}. If ComfyUI does not list it, restart ComfyUI.")
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
            w["label"].configure(text={"verifying": "checking", "queued": "queued"}.get(info["state"], pct))
        except (tk.TclError, KeyError):      # noqa: F405
            pass
