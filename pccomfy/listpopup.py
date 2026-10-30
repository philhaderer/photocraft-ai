"""A list that opens under a button: rows that light up under the mouse, a click takes one, the mouse wheel and a thin
scroll bar move through a long list (the clock in the header, user 30.10.; a tk.Menu can do neither).

Rows are (text, command, kind) with kind "item", "action" (the first row, "Erase history": muted, a line below it) or
"disabled" (a note). Escape, a click on a row and a click elsewhere in the window close it."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from .gui_common import ACCENT, FG, MUTED, PANEL, ThinScrollbar, font

MAX_ROWS = 10       # rows shown before the list scrolls
HOT_FG = "#1b1b1b"


class ListPopup:
    def __init__(self, root, anchor, rows: list[tuple[str, Callable | None, str]], scale: float = 1.0, max_rows: int = MAX_ROWS):
        self.root, self.top, self.closed = root, None, False
        px = lambda n: round(n * scale)  # noqa: E731
        top = self.top = tk.Toplevel(root)
        top.wm_overrideredirect(True)
        top.configure(bg=PANEL, highlightthickness=1, highlightbackground="#5c5c5c")
        cv = tk.Canvas(top, bg=PANEL, highlightthickness=0, bd=0)
        bar = ThinScrollbar(top, cv, px(6), PANEL, auto=True)
        cv.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(cv, bg=PANEL)
        cv.create_window(0, 0, window=inner, anchor="nw")
        self.rows = []
        for text, command, kind in rows:
            lb = tk.Label(inner, text=text, anchor="w", bg=PANEL, fg=MUTED if kind in ("action", "disabled") else FG,
                          font=font(10), padx=px(10), pady=px(3), cursor="arrow" if kind == "disabled" else "hand2")
            lb.pack(fill="x")
            self.rows.append(lb)
            if kind != "disabled":
                lb.bind("<Enter>", lambda e, w=lb: w.configure(bg=ACCENT, fg=HOT_FG))
                lb.bind("<Leave>", lambda e, w=lb, k=kind: w.configure(bg=PANEL, fg=MUTED if k == "action" else FG))
                lb.bind("<Button-1>", lambda e, c=command: self._take(c))
            if kind == "action":
                tk.Frame(inner, bg="#454545", height=1).pack(fill="x", pady=(1, 1))
        for w in (cv, inner, *self.rows):
            w.bind("<MouseWheel>", lambda e: (cv.yview_scroll(-1 if e.delta > 0 else 1, "units"), "break")[1])
        top.update_idletasks()
        w, h = inner.winfo_reqwidth(), inner.winfo_reqheight()
        row_h = max(1, self.rows[0].winfo_reqheight()) if self.rows else 1
        view_h = min(h, row_h * max_rows + (1 if rows and rows[0][2] == "action" else 0) + 3)
        cv.configure(width=w, height=view_h, scrollregion=(0, 0, w, h))
        x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height()
        try:                                  # inside the screen: a list at the right edge opens to the left of its button
            right = root.winfo_vrootx() + root.winfo_vrootwidth()
            x = max(root.winfo_vrootx(), min(x, right - w - px(14)))
        except (tk.TclError, TypeError):
            pass
        top.wm_geometry(f"+{x}+{y}")
        top.bind("<Escape>", lambda e: self.close())
        top.bind("<FocusOut>", lambda e: root.after(150, self._lost_focus))
        top.focus_force()

    def _take(self, command):
        self.close()
        if command:
            command()

    def _lost_focus(self):
        if self.closed:
            return
        try:
            if self.top.focus_displayof() is not None:
                return
        except Exception:  # noqa: BLE001
            pass
        self.close()

    def close(self):
        self.closed = True
        try:
            self.top.destroy()
        except Exception:  # noqa: BLE001
            pass
