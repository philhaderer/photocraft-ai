"""Look and sizing: ttk style, scaling, small widget builders, content size. (moved out of gui.py unchanged; see PLAN.md, phase 0)."""
from __future__ import annotations

from .gui_common import *  # noqa: F401,F403
from .gui_common import __all__ as _ALL  # noqa: F401
from PIL import Image

from . import icons

ICON_PX = 20       # the window's button icons (vector, icons.py) before the display scaling; the slot icons have their own (19, refslots.py)
HINT_ICON_PX = 14  # the info icon in front of the tip under the prompt: about one text line high
FN_GAP = 8         # room between a function symbol and its text (ttk has no gap option: the symbol gets it on its right)
SPIN_PX = 21       # the chevrons of the spin boxes (50 % larger than the first 14): cut flat, so the field keeps its height
CHECK_PX = 16      # the checkbox square (PhotoCraft's, measured from docs/design/photocraft-checkbox.png at 150 %)
CHECK_GAP = 6      # room between the checkbox and its text


class ThemeMixin:
    # ---------- UI ----------

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        try:        # Tk's own fonts (menus, the list of a drop-down, entries without a font of their own): ours too
            import tkinter.font as tkfont
            family, size = font(9)[:2]
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                         "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
                tkfont.nametofont(name, root=self.root).configure(family=family, size=size)
        except Exception:
            pass
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, bordercolor="#454545",
                    lightcolor=PANEL, darkcolor=PANEL, troughcolor=PANEL, focuscolor=ACCENT, font=font(10))
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", foreground=MUTED, font=font(9))
        # the rows of the settings window (ui_settings.py): a bold model line, green / red / orange marks, grey details
        # only the headings are bold; everything else in the window is one size smaller (user 31.10.)
        s.configure("SetHead.TLabel", foreground=FG, font=font(10, bold=True))
        s.configure("SetText.TLabel", foreground=FG, font=font(9))
        s.configure("SetText.TCheckbutton", font=font(9))
        s.configure("SetSmall.TButton", padding=(8, 2), width=0, font=font(9))      # Undo and Reset: small, not stretched
        for name, colour in (("SetOk", DONE_GREEN), ("SetBad", ERROR_TEXT), ("SetNote", ACCENT), ("SetMuted", MUTED)):
            s.configure(f"{name}.TLabel", foreground=colour, font=font(9))
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0))     # the tabs of the settings window
        s.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(14, 4), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", ACCENT), ("active", "#5f5f5f")], foreground=[("selected", "#1b1b1b")])
        for name, colour in (("ConnOk", DONE_GREEN), ("ConnBad", ERROR), ("ConnWait", MUTED)):     # the ComfyUI dot
            s.configure(f"{name}.TLabel", foreground=colour, font=font(9))
        s.configure("Badge.TLabel", background=ERROR, foreground="white", font=font(10, bold=True))
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
        s.configure("Tab.Toolbutton", background=PANEL, foreground=FG, padding=(8, 5), anchor="w", relief="flat",
                    borderwidth=0, font=font(10))
        s.map("Tab.Toolbutton", background=[("selected", ACCENT), ("active", "#5f5f5f")],
              foreground=[("selected", "#1b1b1b")])
        s.configure("Link.TButton", background=BG, foreground=MUTED, padding=(0, 2), borderwidth=0, relief="flat",
                    width=0)   # as wide as its text: clam's minimum width would centre "Advanced" and push it right
        s.map("Link.TButton", foreground=[("active", FG)], background=[("active", BG)])
        s.configure("Small.TButton", padding=(8, 2), font=font(9))   # "Show feather" beside the layer mask menu: a button in the size of the slider texts
        # small switches in the look of "Show feather", the chosen one filled orange like the functions (Upscale factor)
        s.configure("Small.Toolbutton", background=PANEL, foreground=FG, padding=(8, 2), font=font(9), anchor="center",
                    relief="flat", borderwidth=0)
        s.map("Small.Toolbutton", background=[("selected", ACCENT), ("active", "#5f5f5f")],
              foreground=[("selected", "#1b1b1b")])
        # the model chips under the functions: outlined, no fill; chosen = orange outline and text (Tab.Toolbutton is the
        # filled look of the functions above them)
        s.configure("Chip.Toolbutton", background=BG, foreground=FG, padding=(2, 3), anchor="center", relief="solid",
                    borderwidth=1, bordercolor="#686868", lightcolor=BG, darkcolor=BG, font=font(9))
        s.map("Chip.Toolbutton", foreground=[("disabled", DISABLED), ("selected", ACCENT)],
              bordercolor=[("disabled", "#4a4a4a"), ("selected", ACCENT)], background=[("active", "#5f5f5f")])
        s.configure("Missing.Chip.Toolbutton", foreground=NA_RED)
        s.configure("Accent.TButton", background=ACCENT, foreground="#1b1b1b", font=font(10, bold=True))
        s.map("Accent.TButton", background=[("active", "#ff9d3d"), ("disabled", "#6e6558")])
        s.configure("Split.Accent.TButton", padding=(6, 6))     # the narrow "×2 ▾" piece on the right of Generate
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
        s.configure("Done.TLabel", foreground=DONE_GREEN, font=font(10, bold=True))      # the word "Done"
        s.configure("DoneRest.TLabel", foreground=FG, font=font(10, bold=True))        # what follows it (seed, layers, time)
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
        s.configure("Value.TLabel", background=PANEL, foreground=FG, padding=(4, 1), font=font(9))
        s.configure("Value.TEntry", fieldbackground=PANEL, foreground=FG, padding=(4, 1), bordercolor=PANEL,
                    lightcolor=PANEL, darkcolor=PANEL, insertcolor=FG)       # the same box, and you can type into it (ValueBox)
        s.map("Value.TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              foreground=[("disabled", DISABLED)], fieldbackground=[("disabled", BG)])
        s.map("TButton", foreground=[("disabled", DISABLED)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self._spin_arrows(s)
        self._checkbox_look(s)

    def _checkbox_look(self, s):
        """Every checkbox in PhotoCraft's look (docs/design/photocraft-checkbox.png): a rounded square with a light grey
        border on a darker field; ticked = filled orange with a white tick (PhotoCraft's is blue); a lighter border under
        the mouse, grey when greyed out. Without image support clam's own indicator stays."""
        try:
            px = self._px(CHECK_PX)
            looks = {"off": ("#454545", "#a0a0a0", None), "off-hover": ("#454545", FG, None),
                     "on": (ACCENT, ACCENT, "#ffffff"), "off-grey": (BG, "#6e6e6e", None),
                     "on-grey": ("#6e6558", "#6e6558", "#a8a8a8")}
            imgs = {}
            for k, v in looks.items():      # the gap to the text is part of the picture (an image element ignores padding)
                wide = Image.new("RGBA", (px + self._px(CHECK_GAP), px), (0, 0, 0, 0))
                wide.paste(icons.checkbox(*v, px), (0, 0))
                imgs[k] = icons.photo(self.root, None, "", px, image=wide)
            self._check_imgs = imgs         # Tk drops an image Python no longer holds
            if "PC.Checkbutton.indicator" not in s.element_names():
                s.element_create("PC.Checkbutton.indicator", "image", imgs["off"],
                                 ("disabled", "selected", imgs["on-grey"]), ("disabled", imgs["off-grey"]),
                                 ("selected", imgs["on"]), ("active", imgs["off-hover"]), sticky="")
            s.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("PC.Checkbutton.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                    ("Checkbutton.label", {"sticky": "nswe"})]})]})])
        except Exception:
            pass

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

    def _function_icon(self, key: str):
        """The symbol of a function button: the user's picture pccomfy/assets/functions/<key>.png when it is there, else the
        shape fn-<key> (icons.py), else a placeholder, with FN_GAP of room on its right. Light on the dark button, dark on the orange (selected) one, grey when
        greyed out."""
        from pathlib import Path
        path = Path(__file__).resolve().parent / "assets" / "functions" / f"{key}.png"
        cache = self.__dict__.setdefault("_icon_cache", {})

        def img(c):
            k = ("fn", key, c)
            if k not in cache:
                px = self._px(ICON_PX)
                pic = None
                if path.exists():
                    try:
                        pic = icons.from_file(path, c, px)
                    except OSError:
                        pic = None
                if pic is None:
                    pic = icons.render(f"fn-{key}" if f"fn-{key}" in icons.SHAPES else "placeholder", c, px)
                wide = Image.new("RGBA", (px + self._px(FN_GAP), px), (0, 0, 0, 0))
                wide.paste(pic, (0, 0))
                cache[k] = icons.photo(self.root, None, c, px, image=wide)
            return cache[k]
        return (img(FG), "selected", img("#1b1b1b"), "disabled", img(DISABLED))

    def _slider_row(self, frame):
        """Sharpen, Match colours, Edge feather and Mix source/new share one layout: the label takes the room on the left,
        the slider (SLIDER_W) and its value box sit on the right, so all bars are equally long and end at the same place
        (the LoRA sliders beside their checkboxes too)."""
        frame.columnconfigure(0, weight=1)

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
                    font=font(10), padx=6, pady=4, undo=True, maxundo=200)
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
        if getattr(self, "_minimized", False):          # only the header: exactly its height
            w, h = self._px(MIN_W), self.root.winfo_reqheight()
            if getattr(self, "_geom", None) != (w, h):
                self._geom = (w, h)
                self.root.geometry(f"{w}x{h}")
            return
        cv, sb = getattr(self, "cv_body", None), getattr(self, "sb_body", None)
        if cv is not None and sb is not None:
            body = self.f_body.winfo_reqheight()
            if isinstance(body, int) and body > 1:
                # the target height straight away: setting the full height first and then a smaller one changed the
                # canvas twice per call, and each change asked for the next fit (a loop every 60 ms: flicker, a jumping bar)
                try:
                    cur = int(float(cv.cget("height")))
                except (TypeError, ValueError, tk.TclError):
                    cur = body
                others = self.root.winfo_reqheight() - cur          # everything but the scrolled body
                room = self._max_height() - others if isinstance(others, int) else body
                target = body if body <= room else max(self._px(120), room)
                if target != cur:
                    cv.configure(height=target)
                if target < body:
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
