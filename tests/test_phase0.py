"""Phase 0 (gui.py split, models fields, Expand off for Flux 3 / Krea 2, footer without document count).
Run: python tests/test_phase0.py"""
import queue
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets  # noqa: F401  (installs the tkinter stubs)
from pccomfy import gui, models
from pccomfy import gui_lora, gui_modes, gui_prompt, gui_run, gui_state, gui_theme

# 1. App is assembled from the six mixins and no method is defined twice
mixins = (gui_theme.ThemeMixin, gui_prompt.PromptMixin, gui_lora.LoraMixin, gui_modes.ModeMixin, gui_state.StateMixin, gui_run.RunMixin)
from pccomfy import ui_settings
# L1: SettingsMixin and (L2) RefSlotsMixin stand in front on purpose: they wrap some methods and call super(), so they are left out of the "defined twice" check
# (SettingsMixin brings the download buttons as its own base, DownloadMixin: it stands right behind it)
# EasyMixin (Easy Mode) stands first of all: it wraps methods of the others with super()
assert gui.App.__mro__[1].__name__ == "EasyMixin" and gui.App.__mro__[2] is ui_settings.SettingsMixin and gui.App.__mro__[3].__name__ == "DownloadMixin", gui.App.__mro__
assert gui.App.__mro__[4].__name__ == "RefSlotsMixin" and gui.App.__mro__[5:11] == mixins, gui.App.__mro__
names = [n for m in mixins + (gui.App,) for n in vars(m) if callable(vars(m)[n]) and not n.startswith("__")]
dup = sorted({n for n in names if names.count(n) > 1})
assert not (set(vars(gui.RefSlotsMixin)) & set(names) - {"_on_mode_ui", "_request"}), "RefSlotsMixin wraps only these two (with super())"
assert not dup, f"defined twice: {dup}"
assert len(names) == 167, len(names)      # 106 methods of the old App (without __init__), + _on_body_size and _max_height (scroll bar), + _clear_prompt, + _dialog, + _icon and _spin_arrows, - _scale_clicks (Slider), + _show_pl_line, + _place_window, _place_at_owner and _remember_pos, + _function_icon, _custom_workflow, _update_model_chips, _model_for_mode and _remember_model_for_mode (function first), + toggle_feather_preview, _refresh_feather_preview and _feather_done (feather preview), + _mode_denoise (Reset), + _on_context and _show_context (Context slider), + _pack_post (Context under Edge feather), + _on_density (Mask density), + _lora_strength and _lora_strength_text (LoRA fields), + _needs_description and describe_scene (Krea 2 / MOSS Expand), + _seam_mode (seam correction per model), + _checkbox_look (PhotoCraft checkbox), + _show_variants and _variants_menu (Variants on Generate), + toggle_minimize (header), + _on_turbo (LoRA switch sets steps), + _chip_menu and _set_model_hidden (right-click on the model chips), + copy_canvas (header), + _show_preview and _hide_preview (live preview), + _switch_missing and _enforce_switch_files (switches grey while their files are missing), + _save_page and _load_default_page (chip menu: saved settings per page), + _drop_focus (no focus ring after a click), + _llm_file, _update_llm_button and describe_canvas (LLM button), + _history_begin, _history_end, _history_menu, _history_rows, erase_history and load_history (the last runs), + _below_prompt (LLM row under the prompt), + _llm_row_wanted (row only with a text model), + _drag_start and _drag_move (no title bar), + _set_last_seed and use_last_seed (icon beside the seed), + _reset_click and _reset_settings (Shift + Reset page), + _build_styles_menus, _update_styles_button, _styles_menu, _apply_style, _style_text_at, _style_preview and _style_tip_hide (Styles button), + _monitor_at, _place_native and _menu_span (hover box beside the real menu); - the preset functions (removed 1.11.: refresh_presets, save_preset, save_preset_as, _write_preset, _preset_path, load_preset, delete_preset, preset_blocked; the hidden preset bar)

# 2. what the other tests and callers read from gui.py is still there
for name in ("BUILTIN", "MODE_LABELS", "SHORT_MODES", "LAYER_MASKS", "CLIP_DEFAULT", "ACCENT", "PROMPT_LINES", "FILL_CONTEXT",
             "word_left", "word_right", "sweep_requests", "duration_text", "scale_text", "parse_list", "winlink", "Tooltip", "run_gui", "DONE_GREEN"):
    assert hasattr(gui, name), name

# 3. models: Expand is on for Flux 3 (26.10.), off for Krea 2 and MOSS (blind test 29.10.); the new fields start neutral
by = models.BY_KEY
assert list(by["flux3"].modes) == ["txt2img", "edit", "multi_edit", "remove", "outpaint", "upscale"]
assert list(by["krea2"].modes) == ["txt2img"]
assert list(by["flux2"].modes) == ["txt2img", "edit", "multi_edit", "remove", "outpaint", "upscale", "refine"]
assert list(by["qwen"].modes) == ["txt2img", "edit", "multi_edit", "inpaint", "outpaint", "remove"]
assert list(by["moss"].modes) == ["txt2img"]
assert [m.key for m in models.MODELS] == ["flux3", "flux2", "qwen", "fibo", "krea2", "moss"]
for m in models.MODELS:
    assert isinstance(m.requires, tuple) and m.requires, m.key      # L1 filled requires (the file names per tab); test_detection.py checks them
    assert (m.max_refs == 0) == (m.tag_style == ""), m.key          # L2: a model with slots names its images
assert {k: (m.max_refs, m.tag_style) for k, m in by.items()} == {
    "qwen": (8, "<image{n}>"), "fibo": (2, "<image_{n}>"), "flux2": (3, "image {n}"), "flux3": (3, "<ref_image_{i}>"),
    "krea2": (0, ""), "moss": (0, "")}                                                          # Multi Image Edit: slots per model
assert "Expand" in by["flux3"].tip and "Expand" not in by["krea2"].tip and "Expand" not in by["moss"].tip
assert set(models.PARKED_EXPAND) == {"krea2", "moss"} and all(m.describe for m in models.PARKED_EXPAND.values())   # kept for later


# 4. footer: only "ComfyUI" and its dot (no PhotoCraft mark, no document count)
class FakePC:
    def close(self): pass
    def ping(self): return {"documents": 3}


class FakeComfy:
    def checkpoints(self): return ["a.safetensors"]
    def samplers(self): return ["euler"]
    def clips(self): return []
    def loras(self): return []
    def schedulers(self): return ["normal"]


app = object.__new__(gui.App)
app.pc, app.comfy, app.events = FakePC(), FakeComfy(), queue.Queue()
app.refresh()
kind, info = app.events.get(timeout=5)
assert kind == "refresh" and info["comfy"] is True and "pc" not in info and "err" not in info, info
import threading
for t in threading.enumerate():      # the refresh thread of the fake must end before the interpreter does (a race made the run abort sometimes)
    if t is not threading.current_thread():
        t.join(5)
print("test_phase0 ok")
