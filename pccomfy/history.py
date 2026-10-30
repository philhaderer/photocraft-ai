"""The last 20 runs (PLAN point 13, OpenFill T3b): each finished run keeps every setting of the window, so the clock in the
header can load it again. Decisions of the user (30.10.): the clock symbol in the header; a click loads everything with a
new seed and starts nothing; when the text model wrote the prompt, that text comes back and Enhance is switched off.

Pure data, no Tk: the window (gui_run.py) collects the settings and puts them back. Kept in data/history.json, apart from
runs.jsonl (which is for finding faults)."""
from __future__ import annotations

import json
import time
from pathlib import Path

KEEP = 20
TEXT_W = 44         # characters of the prompt shown in the menu


def load(path: Path) -> list[dict]:
    """The saved runs, newest first; a missing or broken file is an empty list."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict) and isinstance(e.get("settings"), dict)] if isinstance(data, list) else []


def add(path: Path, entry: dict, keep: int = KEEP) -> list[dict]:
    """Put a finished run in front and keep the newest `keep`. A file that cannot be written is left alone."""
    runs = ([entry] + load(path))[:keep]
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(runs, indent=1, ensure_ascii=False), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        pass
    return runs


def entry(title: str, model: str, settings: dict, llm: str = "", now: float | None = None) -> dict:
    """One run: when, its name as in PhotoCraft ("Fill Selection 3"), the model, every setting and the text model's prompt."""
    return {"time": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)), "title": title, "model": model,
            "settings": dict(settings), "llm": (llm or "").strip()}


def label(e: dict, today: str | None = None) -> str:
    """The menu line: "14:22  Fill Selection 3 · Fibo 2.0: a red flower in a vase…" (an older day: "29 Oct 14:22")."""
    stamp = str(e.get("time", ""))
    day, _, clock = stamp.partition(" ")
    today = today or time.strftime("%Y-%m-%d")
    if day and day != today:
        try:
            clock = time.strftime("%d %b ", time.strptime(day, "%Y-%m-%d")).lstrip("0") + clock
        except ValueError:
            pass
    text = " ".join(str(e.get("llm") or e["settings"].get("prompt") or "").split())
    if len(text) > TEXT_W:
        text = text[:TEXT_W - 1].rstrip() + "…"
    name = " · ".join(x for x in (str(e.get("title") or ""), str(e.get("model") or "")) if x)
    return f"{clock}  {name}" + (f": {text}" if text else "")


def settings_to_load(e: dict) -> dict:
    """What a click puts into the window: every setting of the run, a new seed (-1), and the text model's prompt with
    Enhance off when there was one."""
    s = dict(e["settings"])
    s["seed"] = -1
    if e.get("llm"):
        s["prompt"], s["enhance"] = e["llm"], False
    return s
