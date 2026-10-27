"""Configuration: ~/.config/pccomfy/config.toml (every field optional)."""

from __future__ import annotations

import copy
import json
import os
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _config_dir() -> Path:
    """PCCOMFY_HOME wins. On Windows everything lives in <bridge folder>\\data (portable, like PhotoCraft)."""
    env = os.environ.get("PCCOMFY_HOME")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        return _ROOT / "data"
    return Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "pccomfy"


CONFIG_DIR = _config_dir()
# Windows: the workflows shipped next to the code; elsewhere: ~/.config/pccomfy/workflows
WORKFLOWS_DIR = _ROOT / "workflows" if os.name == "nt" else CONFIG_DIR / "workflows"
# Windows: <bridge folder>\\presets (outside data\\, so git tracks them); elsewhere: ~/.config/pccomfy/presets
PRESETS_DIR = _ROOT / "presets" if os.name == "nt" else CONFIG_DIR / "presets"
EXCHANGE_DIR = CONFIG_DIR / "exchange" if os.name == "nt" else Path("~/.cache/pccomfy/exchange")
CONFIG_FILE = CONFIG_DIR / "config.toml"
STATE_FILE = CONFIG_DIR / "state.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"     # what the settings overlay and the tab menu save (model map, favourites ...)

DEFAULTS = {
    "photocraft": {
        "host": "127.0.0.1",
        "port": 7878,
        "token_file": str(CONFIG_DIR / "photocraft.token"),
        "exchange_dir": str(EXCHANGE_DIR),
        "headless": False,
    },
    "comfyui": {
        "url": "http://127.0.0.1:8188",
        "workflows_dir": str(WORKFLOWS_DIR),
    },
    "defaults": {
        "checkpoint": "",
        "negative": "",
        "steps": 25,
        "cfg": 6.0,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "denoise": 0.6,
        "base_res": 1024,
        "context": 0.4,
        "mask_grow": 8,
        "mask_blur": 8,
        "overlap": 48,
        "variants": 1,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path: str | Path | None = None) -> dict:
    p = Path(path).expanduser() if path else CONFIG_FILE
    cfg = DEFAULTS
    if p.exists():
        with open(p, "rb") as f:
            cfg = _merge(DEFAULTS, tomllib.load(f))
    return cfg


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ---------- settings of the settings overlay (data/settings.json, separate from the window state) ----------

def load_settings() -> dict:
    try:
        d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def get_setting(key: str, default=None):
    return load_settings().get(key, default)


def set_setting(key: str, value) -> None:
    s = load_settings()
    if value is None:
        s.pop(key, None)
    else:
        s[key] = value
    save_settings(s)


def model_map() -> dict:
    """The user's own file links: the file name the plugin expects -> the file name ComfyUI lists for it."""
    m = get_setting("model_map", {})
    return {str(k): str(v) for k, v in m.items()} if isinstance(m, dict) else {}


def set_model_link(expected: str, local: str | None) -> None:
    """Link ``expected`` to ``local``; an empty ``local`` removes the link."""
    m = model_map()
    if local:
        m[expected] = local
    else:
        m.pop(expected, None)
    set_setting("model_map", m or None)


def set_model_map(m: dict) -> None:
    """Replace all links at once (Undo / Reset in the settings window)."""
    set_setting("model_map", dict(m) or None)


def extra_paths_file() -> str:
    """The extra_model_paths.yaml the user pointed the overlay at ("" = none)."""
    return str(get_setting("extra_paths_file", "") or "")


def set_extra_paths_file(path: str) -> None:
    set_setting("extra_paths_file", path or None)


# Favourites and hidden tabs: the right-click menu (lane L3) and Easy Mode read and write them only through these.

def favorites() -> dict:
    """Function (mode key) -> the tab key the user prefers for it."""
    f = get_setting("favorites", {})
    return {str(k): str(v) for k, v in f.items()} if isinstance(f, dict) else {}


def set_favorite(mode: str, tab: str | None) -> None:
    f = favorites()
    if tab:
        f[mode] = tab
    else:
        f.pop(mode, None)
    set_setting("favorites", f or None)


def hidden_tabs() -> set:
    h = get_setting("hidden_tabs", [])
    return {str(x) for x in h} if isinstance(h, list) else set()


def set_tab_hidden(tab: str, hidden: bool) -> None:
    h = hidden_tabs()
    (h.add if hidden else h.discard)(tab)
    set_setting("hidden_tabs", sorted(h) or None)
