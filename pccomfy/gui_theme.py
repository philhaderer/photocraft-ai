"""Look and sizing: ttk style, scaling, small widget builders, content size. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401


class ThemeMixin:
    # ---------- UI ----------

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor="#454545",
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, font=(FONT, 10))
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", foreground=MUTED, font=(FONT, 9))
        s.configure("Badge.TLabel", background=ERROR, foreground="white", font=(FONT, 10, "bold"))
        s.configure("Error.TLabel", foreground=ERROR_TEXT)
        s.configure("TLabelframe", background=BG, bordercolor="#454545")
        s.configure("TLabelframe.Label", background=BG, foreground=MUTED)
        s.configure("TRadiobutton", background=BG, foreground=FG)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        for w in ("TRadiobutton", "TCheckbutton"):
            s.map(w, background=[("active", BG)], indicatorbackground=[("selected", ACCENT), ("active", "#5f5f5f")],
                  indicatorforeground=[("selected", "#1b1b1b")])
        s.configure("TButton", background=PANEL, foreground=FG, padding=6)
        s.map("TButton", background=[("active", "#5f5f5f")])
        s.configure("Icon.TButton", padding=(6, 4))
        s.configure("Tab.Toolbutton", background=PANEL, foreground=FG, padding=(4, 5), anchor="center", relief="flat",
                    borderwidth=0, font=(FONT, 10))
        s.map("Tab.Toolbutton", background=[("selected", ACCENT), ("active", "#5f5f5f")],
              foreground=[("selected", "#1b1b1b")])
        s.configure("Link.TButton", background=BG, foreground=MUTED, padding=(0, 2), borderwidth=0, relief="flat")
        s.map("Link.TButton", foreground=[("active", FG)], background=[("active", BG)])
        s.configure("Accent.TButton", background=ACCENT, foreground="#1b1b1b", font=(FONT, 10, "bold"))
        s.map("Accent.TButton", background=[("active", "#ff9d3d"), ("disabled", "#6e6558")])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
        s.configure("TCheckbutton", indicatorbackground=PANEL, indicatorforeground=FG)
        s.configure("TRadiobutton", indicatorbackground=PANEL)
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=FG, arrowsize=self._px(18))   # up/down arrows 50 % larger
        s.configure("Horizontal.TProgressbar", background=ACCENT)
        s.configure("Grip.TFrame", background="#454545")
        s.configure("Hint.TLabel", foreground=ACCENT)
        s.configure("Sep.TFrame", background="#9a9a9a")
        s.configure("Done.TLabel", foreground=DONE_GREEN, font=(FONT, 10, "bold"))      # the word "Done"
        s.configure("DoneRest.TLabel", foreground=FG, font=(FONT, 10, "bold"))        # what follows it (seed, layers, time)
        # greyed out must be visible on the dark theme (clam keeps nearly the normal text colour)
        for w in ("TCheckbutton", "TRadiobutton", "TLabel"):
            s.map(w, foreground=[("disabled", DISABLED)])
        for w in ("TCheckbutton", "TRadiobutton"):
            s.map(w, indicatorbackground=[("disabled", BG), ("selected", ACCENT), ("active", "#5f5f5f")],
                  indicatorforeground=[("disabled", DISABLED), ("selected", "#1b1b1b")])
        s.map("TSpinbox", foreground=[("disabled", DISABLED)], fieldbackground=[("disabled", BG)],
              arrowcolor=[("disabled", DISABLED)])
        s.map("TCombobox", foreground=[("disabled", DISABLED), ("readonly", FG)], fieldbackground=[("disabled", BG), ("readonly", PANEL)],
              arrowcolor=[("disabled", DISABLED)])
        # the slider is orange while it works, grey when greyed out (the edge feather: orange = active)
        s.configure("Horizontal.TScale", background=ACCENT, troughcolor="#3a3a3a", bordercolor="#454545",
                    lightcolor=ACCENT, darkcolor=ACCENT)
        s.map("Horizontal.TScale", background=[("disabled", "#6a6a6a")], lightcolor=[("disabled", "#6a6a6a")],
              darkcolor=[("disabled", "#6a6a6a")], troughcolor=[("disabled", BG)])
        s.map("TButton", foreground=[("disabled", DISABLED)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)

    def _scale_clicks(self):
        """A click on a slider's trough moves the handle to where it was clicked (Tk's own behaviour steps by a whole page,
        i.e. to the start or end of a short slider), and dragging follows the mouse."""
        def to_click(e):
            w = e.widget
            try:
                if str(w.cget("state")) == "disabled":
                    return "break"
                lo, hi = float(w.cget("from")), float(w.cget("to"))
                x0, x1 = float(w.coords(lo)[0]), float(w.coords(hi)[0])
                if x1 - x0 < 1:
                    return None
                w.set(lo + min(1.0, max(0.0, (e.x - x0) / (x1 - x0))) * (hi - lo))
            except (tk.TclError, ValueError, TypeError, IndexError, AttributeError):
                return None
            return "break"
        try:
            self.root.bind_class("TScale", "<Button-1>", to_click)
            self.root.bind_class("TScale", "<B1-Motion>", to_click)
        except Exception:
            pass

    def _slider_row(self, frame):
        """Sharpen, Match colours, Edge feather and Mix source/new share one layout: a label column and a value column of fixed
        width, the slider in between, so all bars are equally long and end at the same place on the right."""
        frame.columnconfigure(0, minsize=self._px(158))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, minsize=self._px(60))

    def _open_on_click(self, cb):
        def post(_e=None):
            try:
                if str(cb.cget("state")) == "disabled":
                    return None
                cb.focus_set()
                cb.tk.call("ttk::combobox::Post", str(cb))
            except Exception:
                return None
            return "break"
        cb.bind("<Button-1>", post)

    def _text(self, parent, height):
        t = tk.Text(parent, height=height, width=10, wrap="word", bg=PANEL, fg=FG, insertbackground=FG,
                    relief="flat", highlightthickness=1, highlightbackground="#454545", highlightcolor=ACCENT,
                    font=(FONT, 10), padx=6, pady=4, undo=True, maxundo=200)
        self._editor_keys(t)
        return t

    def _spin(self, parent, var, frm, to, inc=1.0, width=6):
        return ttk.Spinbox(parent, textvariable=var, from_=frm, to=to, increment=inc, width=width)

    def _px(self, n: int) -> int:
        return round(n * getattr(self, "ui", 1.0))

    def _on_content_size(self, _event=None):
        """The content changed its size (a section appeared, text wrapped): fit the window again, once, a moment later."""
        if not getattr(self, "_sized", False) or self._fit_job is not None:
            return

        def fit():
            self._fit_job = None
            try:
                if abs(self.root.winfo_reqheight() - self.root.winfo_height()) > 2:
                    self._fit_height()
            except tk.TclError:
                pass
        self._fit_job = self.root.after(60, fit)

    def _fit_height(self, width: int | None = None):
        """The window is MIN_W wide (fixed) and exactly as high as its content needs."""
        self.root.update_idletasks()
        w, h = self._px(MIN_W), max(self._px(320), self.root.winfo_reqheight())
        self.root.geometry(f"{w}x{h}")

    def _pl_style(self, style: str):
        lbl = getattr(self, "lbl_pl", None)
        if lbl is not None and getattr(self, "_pl_style_now", "") != style:
            self._pl_style_now = style
            lbl.configure(style=style)
