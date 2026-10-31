"""Tip of the day: a small popup when the window starts (PLAN.md point 16), and the matching tick in the settings window.
The tips are in tips.py. The shown ones and the tick are kept in settings.json (state.json is rewritten completely on every save)."""
from __future__ import annotations

import os
import random

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from .tips import TIPS

HIDE_KEY, SHOWN_KEY = "hide_tips", "shown_tips"
HIDE_TEXT = "Don’t show tips at startup"
POPUP_W, POPUP_WRAP = 380, 340           # popup width and text width in px at 100 %


def tips_hidden() -> bool:
    return bool(cfgmod.get_setting(HIDE_KEY, False))


def pick_tip(count: int, shown, rng=random) -> tuple[int, list[int]]:
    """A random tip index that was not shown yet; when all were shown, the round starts again. Returns it and the new shown list."""
    done = [i for i in shown if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < count] if isinstance(shown, list) else []
    left = [i for i in range(count) if i not in done]
    if not left:                                   # all shown: a new round (the tip just shown is not first again)
        last = done[-1] if done else -1
        done, left = [], [i for i in range(count) if i != last] or [0]
    i = rng.choice(left)
    return i, done + [i]


class TipsMixin:
    def _schedule_tip(self):
        """Called once at the end of start-up. Not in tests (PCCOMFY_NO_TIPS=1)."""
        if not os.environ.get("PCCOMFY_NO_TIPS"):
            self.root.after(600, self._show_tip_popup)

    def _show_tip_popup(self):
        if getattr(self, "_closing", False) or getattr(self, "_tip_win", None) or tips_hidden() or not TIPS:
            return
        try:
            if self.root.state() in ("iconic", "withdrawn"):
                return
        except tk.TclError:
            return
        i, shown = pick_tip(len(TIPS), cfgmod.get_setting(SHOWN_KEY, []))
        cfgmod.set_setting(SHOWN_KEY, shown)
        self._build_tip_popup(TIPS[i])

    def _build_tip_popup(self, text: str):
        """The window: the tip, the tick and "OK". The tick is saved at once, so it also holds when the window is just closed."""
        win = tk.Toplevel(self.root)
        win.title("Tip of the day")
        win.wm_overrideredirect(True)                  # no title bar (user 31.10.); the thin frame keeps it visible
        win.configure(bg=BG, highlightthickness=1, highlightbackground="#5c5c5c")
        self._tip_win = win
        v_hide = tk.BooleanVar(value=tips_hidden())
        self._tip_hide_var = v_hide

        def close():
            self._tip_win = None
            try:
                win.destroy()
            except tk.TclError:
                pass

        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=self._px(14), pady=self._px(12))
        ttk.Label(box, text="Tip of the day", font=font(10, bold=True), foreground=ACCENT_TEXT).pack(anchor="w")
        ttk.Label(box, text=text, wraplength=self._px(POPUP_WRAP), justify="left", font=font(10)).pack(anchor="w", pady=(self._px(8), self._px(12)))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Checkbutton(row, text=HIDE_TEXT, variable=v_hide, style="SetText.TCheckbutton",
                        command=lambda: cfgmod.set_setting(HIDE_KEY, True if v_hide.get() else None)).pack(side="left")
        ok = ttk.Button(row, text="OK", command=close, style="TipOk.TButton")
        ok.pack(side="right")
        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Return>", lambda e: close())
        win.bind("<Escape>", lambda e: close())
        try:
            win.transient(self.root)
            win.update_idletasks()
            w, h = max(self._px(POPUP_W), win.winfo_reqwidth()), win.winfo_reqheight()
            x, y = self._tip_position(w, h)
            win.geometry(f"{w}x{h}+{x}+{y}")
            win.focus_force()
            ok.focus_set()
        except tk.TclError:
            pass
        return win

    def _tip_position(self, w: int, h: int) -> tuple[int, int]:
        """Beside the plugin where there is room (right first, then left), not on top of it; with no room on either side it
        goes to the screen edge on the side with more room. Always inside the screen."""
        r = self.root
        gap = self._px(8)
        left, top = r.winfo_vrootx(), r.winfo_vrooty()
        right, bottom = left + r.winfo_vrootwidth(), top + r.winfo_vrootheight()
        rl, rr = r.winfo_rootx(), r.winfo_rootx() + r.winfo_width()
        if right - rr >= w + gap:
            x = rr + gap
        elif rl - left >= w + gap:
            x = rl - gap - w
        else:
            x = right - w if right - rr >= rl - left else left
        y = r.winfo_rooty() + self._px(60)
        return max(left, min(x, right - w)), max(top, min(y, bottom - h))

    def _tips_setting_row(self, parent):
        """The same tick in the settings window (bottom of the window; packed before the notebook so it keeps its place)."""
        self._tips_setting_var = tk.BooleanVar(value=tips_hidden())
        cb = ttk.Checkbutton(parent, text=HIDE_TEXT, variable=self._tips_setting_var, style="SetText.TCheckbutton",
                             command=lambda: cfgmod.set_setting(HIDE_KEY, True if self._tips_setting_var.get() else None))
        cb.pack(side="bottom", anchor="w", padx=10, pady=(0, 8))
        Tooltip(cb, "Tick to stop the tip of the day when the plugin starts; untick to see the tips again.")
        return cb
