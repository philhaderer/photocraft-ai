"""Easy Mode, the logic without a window (PLAN.md point 17, docs/easymode-plan.md).

Easy Mode shows only the function buttons and the prompt; the plugin picks the model. This file holds what can be tested
without Tk: the six functions, the priority of the models per function, the choice of the best installed model, the
visible texts and the saved switch. The window part lives in gui_easy.py.
"""
from __future__ import annotations

from typing import Callable, Iterable

from . import config as cfgmod
from . import models

# The functions Easy Mode offers (user 31.10.: six; Refine and Multi Image Edit are left out).
EASY_MODES = ("txt2img", "edit", "inpaint", "remove", "outpaint", "upscale")

# The models per function, best first (user 31.10., from the "perfect" list and the ranking). Easy Mode uses the first one
# that is offered and not hidden; favourites and saved pages do not count in Easy Mode.
PRIORITY = {
    "txt2img": ("flux3", "moss", "flux2", "qwen", "fibo"),
    "edit": ("flux3", "qwen", "flux2", "fibo"),
    "inpaint": ("fibo", "qwen"),
    "remove": ("fibo", "qwen"),
    "outpaint": ("flux2", "flux3", "qwen", "fibo"),
    "upscale": ("flux3", "flux2"),
}

# Functions Easy Mode leaves out, with the models that do them best first (the list in the Easy Mode tab of the settings).
EXTRA_PRIORITY = {
    "refine": ("fibo", "flux2"),
    "multi_edit": ("flux3", "flux2", "qwen", "fibo"),
}

# The starter models Easy Mode asks for (user 31.10.: Fibo and Flux 3, maybe Qwen later).
STARTER_MODELS = ("flux3", "fibo")

# Visible texts (user 31.10.). Edit them here (user-edits.md).
SWITCH_TEXT = "Easy Mode"
SWITCH_TIP = ("Easy mode: only the basics. The plugin picks the best installed model and its tested settings. "
              "Click again for all settings.")
MODEL_LINE = "{name}"                         # in the footer, right of "Live preview"
MODEL_TIP = "The model Easy Mode picked for this function."
MODE_GREYED_TIP = "No model installed for this function. Get the starter models in the settings (gear) under Easy Mode."
NO_MODELS = "No models yet. Open the settings (gear) and get the starter models."
STATUS_ON = "Easy mode on: the plugin picks the model and settings."
TAB_TITLE = "Easy Mode"
TAB_INFO = "Easy mode needs these models for all six functions."
TAB_BUTTON = "Get the starter models"
TAB_MORE = ("Refine and Multi Image Edit are not in Easy Mode. Switch Easy Mode off to use them; they need one of these "
            "models (best first):")
TAB_FLUX3_NOTE = "Flux 3 needs a free Hugging Face login once. The button opens its page."


def best_model(mode: str, usable: Callable[[str], bool], hidden: Iterable[str] = ()) -> str:
    """The best model for `mode`: the first of PRIORITY that has the function, is usable (all its files are there) and is not
    hidden; '' when there is none (the function is greyed out)."""
    hidden = set(hidden)
    for key in PRIORITY.get(mode, ()):
        m = models.BY_KEY.get(key)
        if m is not None and mode in m.modes and key not in hidden and usable(key):
            return key
    return ""


def available_modes(usable: Callable[[str], bool], hidden: Iterable[str] = ()) -> dict:
    """Each Easy Mode function -> its model key ('' = greyed out)."""
    return {mode: best_model(mode, usable, hidden) for mode in EASY_MODES}


def model_line(model_key: str) -> str:
    """The model's name for the footer, right of "Live preview": 'Fibo 2.0 Edit Turbo' ('' without a model)."""
    m = models.BY_KEY.get(model_key)
    return MODEL_LINE.format(name=m.label) if m else ""


def is_on() -> bool:
    return bool(cfgmod.get_setting("easy_mode", False))


def set_on(on: bool) -> None:
    cfgmod.set_setting("easy_mode", True if on else None)


def save_return(values: dict) -> None:
    """The window state of the normal mode, kept while Easy Mode is on (model, function and the settings)."""
    cfgmod.set_setting("easy_return", dict(values))


def pop_return() -> dict:
    """The kept state of the normal mode, and forget it."""
    v = cfgmod.get_setting("easy_return", {})
    cfgmod.set_setting("easy_return", None)
    return dict(v) if isinstance(v, dict) else {}
