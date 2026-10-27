"""Look and sizing: ttk style, scaling, small widget builders, content size. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from . import icons

ICON_PX = 20       # the window's button icons (vector, icons.py) before the display scaling; the slot icons have their own (24)
SPIN_PX = 14       # the chevrons of the spin boxes: flatter than a button icon, so the field keeps its height


class ThemeMixin:
    # ---------- UI ----------

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor="#454545",
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, font=(FONT, 10))
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", foreground=MUTED, font=(FONT, 9))
        for name, colour in (("ConnOk", DONE_GREEN), ("ConnBad", ERROR), ("ConnWait", MUTED)):     # the ComfyUI dot
            s.configure(f"{name}.TLabel", foreground=colour, font=(FONT, 9))
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
        s.configure("Link.TButton", background=BG, foreground=MUTED, padding=(0, 2), borderwidth=0, relief="flat",
                    width=0)   # as wide as its text: clam's minimum width would centre "Advanced" and push it right
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
        # the value of a slider (Slider, gui_common.py) sits in a small dark box on its right, as in PhotoCraft
        s.configure("Value.TLabel", background=PANEL, foreground=FG, padding=(4, 1), font=(FONT, 9))
        s.map("TButton", foreground=[("disabled", DISABLED)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self._spin_arrows(s)

    def _spin_arrows(self, s):
        """The spin boxes' up/down arrows: thin chevrons (icons.py) instead of clam's big filled triangles; orange under the
        mouse, grey when greyed out. Without image support the theme's own arrows stay."""
        try:
            px = self._px(SPIN_PX)
            imgs = {(up, c): icons.photo(self.root, "", c, px, icons.spin_arrow(up, c, px))
                    for up in (True, False) for c in (FG, ACCENT, DISABLED)}
            self._spin_imgs = imgs          # Tk drops an image Python no longer holds
            for up, name in ((True, "Chev.uparrow"), (False, "Chev.downarrow")):
                if name not in s.element_names():
                    s.element_create(name, "image", imgs[(up, FG)], ("disabled", imgs[(up, DISABLED)]),
                                     ("pressed", imgs[(up, ACCENT)]), ("active", imgs[(up, ACCENT)]),
                                     padding=(self._px(3), self._px(1)))
            s.layout("TSpinbox", [("Spinbox.field", {"side": "top", "sticky": "we", "children": [
                ("null", {"side": "right", "sticky": "", "children": [
                    ("Chev.uparrow", {"side": "top", "sticky": "e"}), ("Chev.downarrow", {"side": "bottom", "sticky": "e"})]}),
                ("Spinbox.padding", {"sticky": "nswe", "children": [("Spinbox.textarea", {"sticky": "nswe"})]})]})])
        except Exception:
            pass

    def _icon(self, kind: str, color: str = FG, px: int = ICON_PX):
        """A button icon (icons.py) at px before the display scaling, as a ttk image spec: `color`, grey when the button is
        greyed out, orange under the mouse (like the slot icons)."""
        cache = self.__dict__.setdefault("_icon_cache", {})

        def img(c):
            if (kind, c, px) not in cache:
                cache[(kind, c, px)] = icons.photo(self.root, kind, c, self._px(px))
            return cache[(kind, c, px)]
        return (img(color), "disabled", img(DISABLED), "active", img(ACCENT))

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
                self._fit_height()
            except tk.TclError:
                pass
        self._fit_job = self.root.after(60, fit)

    def _on_body_size(self, _event=None):
        """The scrolled body changed its size (Advanced opened, a slot row appeared): its scroll area and the window follow."""
        cv = getattr(self, "cv_body", None)
        if cv is not None:
            try:
                cv.configure(scrollregion=cv.bbox("all"))
            except tk.TclError:
                pass
        self._on_content_size()

    def _max_height(self) -> int:
        """The tallest the window may be: down to the bottom of the screen's work area from where the window starts."""
        try:
            top = max(0, int(self.root.winfo_rooty()))
            return max(self._px(320), int(self.root.winfo_screenheight()) - top - self._px(56))   # 56: taskbar and frame
        except (TypeError, ValueError, tk.TclError):
            return 10 ** 6

    def _fit_height(self, width: int | None = None):
        """The window is MIN_W wide (fixed) and exactly as high as its content needs. When that is taller than the screen
        allows, the body under the tabs gets the room that is left and scrolls (thin bar on the right)."""
        self.root.update_idletasks()
        cv, sb = getattr(self, "cv_body", None), getattr(self, "sb_body", None)
        if cv is not None and sb is not None:
            body = self.f_body.winfo_reqheight()
            if isinstance(body, int) and body > 1:
                cv.configure(height=body)
                self.root.update_idletasks()
                over = self.root.winfo_reqheight() - self._max_height()
                if isinstance(over, int) and over > 0:
                    cv.configure(height=max(self._px(120), body - over))
                    sb.show()
                else:
                    sb.hide()
                self.root.update_idletasks()
        empty = bool(getattr(self, "start_state", lambda: "")())      # no model chosen: a small window (tabs, one sentence, footer)
        w, h = self._px(MIN_W), max(self._px(80 if empty else 320), self.root.winfo_reqheight())
        if getattr(self, "_geom", None) != (w, h):
            self._geom = (w, h)
            self.root.geometry(f"{w}x{h}")

    def _pl_style(self, style: str):
        lbl = getattr(self, "lbl_pl", None)
        if lbl is not None and getattr(self, "_pl_style_now", "") != style:
            self._pl_style_now = style
            lbl.configure(style=style)
