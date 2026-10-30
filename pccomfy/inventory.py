"""Model detection: what ComfyUI has installed, and what each tab and mode therefore can do.

``Inventory`` holds one cached reading of the four loader lists (and the node classes) from ComfyUI's /object_info.
Everything here is plain Python, so the tests run it against a fake ComfyUI answer.

Statuses: ``ready`` (nothing missing), ``partial`` (a tab with some modes missing files: those modes are greyed out,
the tab stays usable) and ``missing`` (the tab's own files are missing, or no mode can run).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import manifest, models

LIST_KINDS = tuple(manifest.KINDS)       # unet, clip, vae, lora, preview


def norm(name: str) -> str:
    """Case, separator and spaces tolerant form of a file name."""
    return name.replace("\\", "/").strip().lower()


def resolve(name: str, available: list[str], mapping: dict | None = None, aliases: tuple = ()) -> str | None:
    """The name ComfyUI lists for ``name``, or None. Tries, in this order: the user's own mapping (name -> local file),
    an exact match, a match ignoring case and ``\\`` / ``/``, an alias, and a unique match on the bare file name
    (the file lies in another sub-folder)."""
    if mapping and mapping.get(name) in available:
        return mapping[name]
    if name in available:
        return name
    table = {}
    for a in available:
        table.setdefault(norm(a), a)
    for cand in (name, *aliases):
        if norm(cand) in table:
            return table[norm(cand)]
    for cand in (name, *aliases):
        base = norm(cand).rpartition("/")[2]
        hits = [a for a in available if norm(a).rpartition("/")[2] == base]
        if len(hits) == 1:
            return hits[0]
    return None


@dataclass(frozen=True)
class Status:
    state: str                                   # "ready" | "partial" | "missing"
    missing: tuple = ()                          # manifest.File objects that block it
    optional_missing: tuple = ()                 # manifest.File objects of switches (a note only)
    nodes: tuple = ()                            # missing node classes that block it
    detail: dict = field(default_factory=dict)   # for "partial": mode key -> Status of that mode


class Inventory:
    def __init__(self, lists: dict, nodes=None, mapping: dict | None = None):
        self.lists = {k: list(lists.get(k) or []) for k in LIST_KINDS}
        self.nodes = None if nodes is None else set(nodes)      # None = node classes not read
        self.mapping = dict(mapping or {})

    # ---------- single files ----------

    def found(self, filename: str) -> str | None:
        f = manifest.FILES.get(filename)
        if f is None:
            return None
        return resolve(f.name, self.lists[f.kind], self.mapping, f.aliases)

    def has(self, filename: str) -> bool:
        return self.found(filename) is not None

    def missing(self, names) -> tuple:
        return tuple(manifest.FILES[n] for n in names if n in manifest.FILES and not self.has(n))

    def missing_nodes(self, classes) -> tuple:
        if self.nodes is None:
            return ()
        return tuple(c for c in classes if c not in self.nodes)

    # ---------- tabs and modes ----------

    def mode_status(self, key: str, mode: str) -> Status:
        miss = self.missing(manifest.mode_required(key, mode))
        nodes = self.missing_nodes(manifest.mode_nodes(key, mode))
        opt = self.missing(manifest.mode_optional(key, mode))
        return Status("missing" if (miss or nodes) else "ready", miss, opt, nodes)

    def tab_status(self, key: str) -> Status:
        m = models.BY_KEY.get(key)
        if m is None or key not in manifest.TABS:
            return Status("ready")
        own = self.missing(manifest.tab_required(key))
        if own:
            return Status("missing", own)
        per = {mode: self.mode_status(key, mode) for mode in m.modes}
        bad = {mode: s for mode, s in per.items() if s.state == "missing"}
        opt = self.missing(manifest.TABS[key].optional)
        if not bad:
            return Status("ready", (), opt)
        files = tuple(dict.fromkeys(f for s in bad.values() for f in s.missing))
        nodes = tuple(dict.fromkeys(c for s in bad.values() for c in s.nodes))
        if len(bad) == len(per):
            return Status("missing", files, opt, nodes, bad)
        return Status("partial", files, opt, nodes, bad)

    # ---------- a whole workflow graph ----------

    def check_workflow(self, graph: dict) -> tuple[list, list]:
        """(missing model files as (kind, name), missing node classes) of an API-format graph."""
        files, classes = [], []
        loaders = {cls: (kind, fld) for kind, (cls, fld, _f) in manifest.KINDS.items()}
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            cls = node.get("class_type", "")
            if cls in loaders:
                kind, fld = loaders[cls]
                val = (node.get("inputs") or {}).get(fld)
                if isinstance(val, str) and resolve(val, self.lists[kind], self.mapping) is None and (kind, val) not in files:
                    files.append((kind, val))
            if self.nodes is not None and cls and cls not in self.nodes and cls not in classes:
                classes.append(cls)
        return files, classes

    def apply_names(self, graph: dict) -> int:
        """Rewrite the loader fields of a graph to the names ComfyUI lists (user mapping, other case, other sub-folder).
        Returns how many fields changed. The bridge calls this once before it queues a graph."""
        changed = 0
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            for kind, (cls, fld, _f) in manifest.KINDS.items():
                if node.get("class_type") != cls:
                    continue
                inputs = node.get("inputs") or {}
                val = inputs.get(fld)
                if not isinstance(val, str):
                    continue
                f = manifest.FILES.get(val)
                real = resolve(val, self.lists[kind], self.mapping, f.aliases if f else ())
                if real is not None and real != val:
                    inputs[fld] = real
                    changed += 1
            if node.get("class_type") == "AUSBOSS_NODES_LoraLoader":     # its LoRAs are a JSON list (Flux 3 Restore LoRA)
                inputs = node.get("inputs") or {}
                try:
                    items = json.loads(inputs.get("loras") or "[]")
                except (TypeError, ValueError):
                    continue
                hit = 0
                for lo in items:
                    if isinstance(lo, dict) and isinstance(lo.get("name"), str):
                        f = manifest.FILES.get(lo["name"])
                        real = resolve(lo["name"], self.lists["lora"], self.mapping, f.aliases if f else ())
                        if real is not None and real != lo["name"]:
                            lo["name"] = real
                            hit += 1
                if hit:
                    inputs["loras"] = json.dumps(items)
                    changed += hit
        return changed

    # ---------- the settings overlay ----------

    def rows(self) -> list[dict]:
        """One row per tab for the overlay: its status and every manifest file with found / missing."""
        out = []
        for m in models.MODELS:
            st = self.tab_status(m.key)
            names = list(manifest.TABS[m.key].required) if m.key in manifest.TABS else []
            for mode in (manifest.TABS[m.key].modes if m.key in manifest.TABS else {}):
                names += [n for n in manifest.mode_extra(m.key, mode) if n not in names]
            opt = [n for n in (manifest.TABS[m.key].optional if m.key in manifest.TABS else ()) if n not in names]
            for mode in (manifest.TABS[m.key].modes if m.key in manifest.TABS else {}):
                opt += [n for n in manifest.mode_optional(m.key, mode) if n not in names and n not in opt]
            files = ([(manifest.FILES[n], self.found(n), "required") for n in names if n in manifest.FILES]
                     + [(manifest.FILES[n], self.found(n), "optional") for n in opt
                        if n in manifest.FILES and manifest.FILES[n].kind not in manifest.ADDITIONAL_KINDS])
            kinds = list(manifest.KINDS)       # diffusion models first, then text encoders, VAEs, LoRAs, the rest (user 30.10.)
            files.sort(key=lambda t: kinds.index(t[0].kind))     # stable: required before optional within a kind
            out.append({"key": m.key, "label": m.label, "status": st, "files": files})
        return out

    def additional_rows(self) -> list[tuple]:
        """The helpers several models share ("Additional models"): (file, found, what it is for, model keys using it)."""
        return [(f, self.found(f.name), manifest.ADDITIONAL_KINDS[f.kind], manifest.used_by(f.name))
                for f in manifest.FILES.values() if f.kind in manifest.ADDITIONAL_KINDS and manifest.used_by(f.name)]


# ---------- reading ComfyUI ----------

def fetch(comfy, mapping: dict | None = None) -> Inventory:
    """Read the lists from a ``comfy.ComfyUI``. Raises ComfyError when the server cannot be reached."""
    raw = comfy.inventory_raw()
    if os.environ.get("PCCOMFY_SIMULATE_NO_MODELS"):    # test start of a new user ("photocraft-ai neuer-nutzer.bat"):
        raw = {**raw, **{k: [] for k in LIST_KINDS}}     # ComfyUI answers, but its model folders look empty
    return Inventory({k: raw.get(k) for k in LIST_KINDS}, raw.get("nodes"), mapping)


# ---------- messages ----------

def _one(f: manifest.File) -> str:
    s = f"{f.name} -> ComfyUI\\{f.target}"
    if f.url:
        s += f" (download: {f.url})"
    return s


def preflight(inv: Inventory | None, key: str, mode: str) -> list[str]:
    """What stops a run of this tab and mode, as readable lines (empty = go). A tab that is not in the manifest (a workflow
    of your own) and an inventory that was never read (ComfyUI not reachable) never stop anything."""
    if inv is None or key not in manifest.TABS:
        return []
    lines = [f"missing: {_one(f)}" for f in inv.missing(manifest.mode_required(key, mode))]
    lines += [f"missing node {c}" + (f": install {p[0]}" + (f" ({p[1]})" if p[1] else "") if (p := manifest.node_pack(c)) else "")
              for c in inv.missing_nodes(manifest.mode_nodes(key, mode))]
    return lines


def short_message(lines: list[str], label: str = "") -> str:
    """The one clear status line: the first problem with its folder and link, the rest only counted."""
    if not lines:
        return ""
    head = (label + ": " if label else "") + lines[0]
    more = len(lines) - 1
    return head + (f" (+{more} more, see Settings)" if more else "") + ". Restart ComfyUI after copying files."


def tooltip_text(st: Status, what: str = "") -> str:
    """The extra tooltip lines of a greyed-out tab or mode."""
    if st.state == "ready":
        return ""
    names = [f.name for f in st.missing] + list(st.nodes)
    shown = ", ".join(names[:3]) + (f" (+{len(names) - 3} more)" if len(names) > 3 else "")
    return f"Missing{(' for ' + what) if what else ''}: {shown}. Set in settings (gear)."


# ---------- helpers ----------

def load_workflow(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
