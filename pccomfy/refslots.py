"""Reference images for Multi Image Edit: the slots (pure logic) and, further down, the Tk widget.

The picture in PhotoCraft is image 1; the reference images are image 2, 3 ... How a model names them in the prompt comes
from `Model.tag_style` ("<image{n}>", "image {n}", "<ref_image_{i}>": `{n}` counts from 1, `{i}` from 0), how many it takes
from `Model.max_refs`. Everything here that does not need Tk is tested on any system (tests/test_refslots.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from . import clipboard

MAX_SIDE = 1024                      # the longest side of a reference image sent to the model
# What shows where a reference image is transparent (a cut-out, a PNG with alpha): neutral mid grey. The ONE place to change it;
# the model gets a flat picture, and white behind a cut-out subject disturbed it.
DEFAULT_BACKGROUND = (128, 128, 128)


# ---- rewriting the image names in the prompt when the model changes ----

MAX_TAG = 9      # image numbers that count as a tag (1 = the picture ... 9); at least the most slots of any model + 1


def _tag_regex(style: str) -> "re.Pattern[str]":
    """A pattern for the tags of one naming rule ("<image{n}>", "image {n}", "<ref_image_{i}>"); the number is group 1."""
    parts = re.split(r"(\{n\}|\{i\})", style)
    pat = "".join(r"(\d{1,2})" if x in ("{n}", "{i}") else re.escape(x) for x in parts)
    if style[0].isalnum():
        pat = r"(?<![\w<])" + pat          # "image 2" is a tag, "myimage 2" is not
    if style[-1].isalnum() or style.rstrip().endswith("}"):
        pat += r"(?!\d)"
    return re.compile(pat)


def retag(text: str, old_style: str, new_style: str) -> str:
    """The prompt with every image name of the rule `old_style` written by the rule `new_style`. Only real tags change (the
    exact pattern of the old rule, number 1..MAX_TAG); the numbering is converted (image 1 is the picture: "<image2>" = "image 2" =
    "<ref_image_1>"), so going there and back gives the same text."""
    if not text or not old_style or not new_style or old_style == new_style:
        return text
    old_zero = "{i}" in old_style

    def conv(m):
        number = int(m.group(1)) + (1 if old_zero else 0)          # 1 = the picture
        if not 1 <= number <= MAX_TAG:
            return m.group(0)
        return new_style.format(n=number, i=number - 1)
    return _tag_regex(old_style).sub(conv, text)


class RefError(ValueError):
    pass


def flatten(im: Image.Image, background=DEFAULT_BACKGROUND) -> Image.Image:
    """RGB copy; transparent areas show `background`."""
    return clipboard.flatten(im, background)


def prepare_image(im: Image.Image, multiple: int = 16, max_side: int = MAX_SIDE, background=DEFAULT_BACKGROUND) -> Image.Image:
    """The reference image as it is sent: flat RGB, at most `max_side` px on the longer side, both sides a multiple of
    `multiple` (Qwen Image 2.1 needs 32; any other size shifts the edit). Never smaller than one `multiple`."""
    rgb = flatten(im, background)
    w, h = rgb.size
    k = min(1.0, max_side / max(w, h))
    nw = max(multiple, int(w * k) // multiple * multiple)
    nh = max(multiple, int(h * k) // multiple * multiple)
    return rgb if (nw, nh) == (w, h) else rgb.resize((nw, nh), Image.LANCZOS)


def parse_drop_data(data: str) -> list[Path]:
    """The paths in a drop event of tkinterdnd2: a Tcl list, names with spaces are wrapped in {braces}."""
    out, rest = [], data.strip()
    while rest:
        if rest[0] == "{":
            end = rest.find("}")
            end = len(rest) if end < 0 else end
            out.append(Path(rest[1:end]))
            rest = rest[end + 1:].lstrip()
        else:
            m = re.match(r"\S+", rest)
            out.append(Path(m.group(0)))
            rest = rest[m.end():].lstrip()
    return out


@dataclass
class RefImage:
    image: Image.Image               # what is sent (a cut-out replaces it; the original stays in `original`)
    name: str = ""                   # where it came from (file name, "clipboard")
    original: Image.Image | None = None
    description: str = ""            # what Qwen 3.5 9B says the picture shows (the "Describe" button)

    @property
    def cut_out(self) -> bool:
        return self.original is not None


@dataclass
class RefSlots:
    """The reference images of one window and the model's limits. More images than the model has slots are kept (so a
    switch of the tab loses nothing) but only the first `max_refs` are sent (`active`)."""
    max_refs: int = 0
    tag_style: str = ""
    items: list = field(default_factory=list)

    def set_model(self, max_refs: int, tag_style: str) -> None:
        self.max_refs, self.tag_style = int(max_refs), tag_style

    @property
    def active(self) -> list:
        return self.items[: self.max_refs]

    @property
    def overflow(self) -> list:
        return self.items[self.max_refs:]

    @property
    def free(self) -> int:
        return max(0, self.max_refs - len(self.items))

    def add(self, image: Image.Image, name: str = "", index: int | None = None) -> int:
        if self.max_refs <= 0:
            raise RefError("This model takes no reference images.")
        if len(self.items) >= self.max_refs:
            raise RefError(f"All {self.max_refs} reference slots are full. Remove one first.")
        item = RefImage(image.convert("RGBA") if image.mode not in ("RGB", "RGBA") else image.copy(), name)
        i = len(self.items) if index is None else max(0, min(index, len(self.items)))
        self.items.insert(i, item)
        return i

    def put(self, i: int, image: Image.Image, name: str = "") -> int:
        """A new picture in filled slot `i` (a drop onto it): its cut-out and description go, its place stays."""
        self.items[i] = RefImage(image.convert("RGBA") if image.mode not in ("RGB", "RGBA") else image.copy(), name)
        return i

    def add_file(self, path, at: int | None = None) -> int:
        """A picture file into the next free slot, or in place of filled slot `at`."""
        p = Path(path)
        if p.suffix.lower() not in clipboard.IMAGE_SUFFIXES or not p.is_file():
            raise RefError(f"{p.name}: not a picture file.")
        with Image.open(p) as im:
            im.load()
            if at is not None and 0 <= at < len(self.items):
                return self.put(at, im, p.name)
            return self.add(im, p.name)

    def add_files(self, paths, at: int | None = None) -> tuple[int, list[str]]:
        """Drop of several files: as many as fit. Dropped onto filled slot `at`, the first picture replaces it and the
        others are added behind the last slot. Returns (how many were taken, messages for the ones that were not)."""
        n, notes = 0, []
        for p in paths:
            try:
                self.add_file(p, at)
                at = None
                n += 1
            except (RefError, OSError) as e:
                notes.append(str(e))
                if isinstance(e, RefError) and "full" in str(e):
                    break
        return n, notes

    def remove(self, i: int) -> None:
        del self.items[i]

    def move(self, i: int, j: int) -> None:
        self.items.insert(max(0, min(j, len(self.items) - 1)), self.items.pop(i))

    def clear(self) -> None:
        self.items.clear()

    def replace(self, i: int, image: Image.Image) -> None:
        """A changed picture (cut-out); the first version is kept for `revert`."""
        it = self.items[i]
        if it.original is None:
            it.original = it.image
        it.image = image

    def revert(self, i: int) -> None:
        it = self.items[i]
        if it.original is not None:
            it.image, it.original = it.original, None

    # ---- names in the prompt ----

    def tag(self, i: int) -> str:
        """How the model names reference image `i` (0-based) in the prompt; "" when it needs no names."""
        if not self.tag_style:
            return ""
        return self.tag_style.format(n=i + 2, i=i + 1)

    def picture_tag(self) -> str:
        return self.tag_style.format(n=1, i=0) if self.tag_style else ""

    def hint(self) -> str:
        """One line for the window: which names to use ("Picture = <image1>, reference 1 = <image2>")."""
        if not self.tag_style or not self.active:
            return ""
        parts = [f"picture = {self.picture_tag()}"] + [f"reference {k + 1} = {self.tag(k)}" for k in range(len(self.active))]
        return ", ".join(parts)

    # ---- the descriptions in the prompt ----

    def description_lines(self) -> list[str]:
        """One line per described image that is sent: "<image2>: a brown dog on grass"."""
        return [f"{self.tag(k) or f'image {k + 2}'}: {it.description}" for k, it in enumerate(self.active) if it.description]

    def prompt_with_descriptions(self, text: str) -> str:
        """The typed text plus the descriptions at its end, one per line: what the prompt field holds after describing every
        image once (see docs/prompt-aufbau.md)."""
        lines = self.description_lines()
        if not lines:
            return text
        return (text.rstrip() + "\n" if text.strip() else "") + "\n".join(lines)

    def put_description(self, text: str, k: int, old: str = "") -> str:
        """The prompt field's text with the description line of image k ("<image2>: a brown dog") written into it. The first
        description goes at the end; a new one replaces the line of the `old` one. When that line was edited or deleted by
        hand, the text stays as it is (the user's words win). The field is what is sent."""
        if not 0 <= k < len(self.items) or not self.items[k].description:
            return text
        name = self.tag(k) or f"image {k + 2}"
        line = f"{name}: {self.items[k].description}"
        if old:
            lines = text.split("\n")
            for j, ln in enumerate(lines):
                if ln.strip() == f"{name}: {old}":
                    lines[j] = line
                    return "\n".join(lines)
            return text
        return (text.rstrip() + "\n" if text.strip() else "") + line

    # ---- what the bridge sends ----

    def images(self) -> list[Image.Image]:
        return [it.image for it in self.active]


# ======================================================================================================================
# Pure helpers for the widget (tested without Tk)
# ======================================================================================================================

def thumbnail_png(image: Image.Image, size: int, background=(0x28, 0x28, 0x28)) -> bytes:   # the colour of gui_common.PANEL (the slot box behind the thumbnail)
    """A PNG of the picture that fits into a size x size square (kept proportional), transparency shown on `background`."""
    import io
    t = flatten(image, background)
    t.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    t.save(buf, "PNG")
    return buf.getvalue()


PREVIEW_ZOOM = 5    # the larger view is 500 % of the slot picture (user 28.10.)


def preview_size(image_size: tuple[int, int], thumb_px: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Size of the larger view: the picture at PREVIEW_ZOOM times its size in the slot (whose longer side is `thumb_px`, or
    less for a small picture), shrunk to fit max_w x max_h (user 28.10.: at most twice as wide as the plugin and as tall as it)."""
    w, h = max(1, image_size[0]), max(1, image_size[1])
    s = min(1.0, thumb_px / max(w, h)) * PREVIEW_ZOOM
    s = min(s, max_w / w, max_h / h)
    return max(1, round(w * s)), max(1, round(h * s))


def preview_position(win: tuple[int, int, int, int], size: tuple[int, int], screen_left: int, screen_right: int,
                     gap: int = 8) -> tuple[int, int]:
    """Top left corner of the larger view: beside the plugin window (x, y, w, h), level with its top; on the left when it
    fits on the screen there (the plugin usually sits at PhotoCraft's right edge), else on the right, else at the screen's
    left edge."""
    x, y, w, _ = win
    left = x - gap - size[0]
    if left >= screen_left:
        return left, y
    if x + w + gap + size[0] <= screen_right:
        return x + w + gap, y
    return screen_left, y



# ======================================================================================================================
# The window part (Tk): one hook in gui.py puts RefSlotsMixin in front of the window's other mixins
# ======================================================================================================================

MULTI_MODE = "multi_edit"     # the window mode that shows the slots (it runs as a whole-image edit)


class RefSlotsMixin:
    """The reference slots of the window. Built the first time the window shows them (`_refs_ensure`), so the hook in gui.py
    is only the class line: `_on_mode_ui` (called on every tab / mode change) and `_request` are wrapped here.
    A slot takes a picture by drag and drop (tkinterdnd2, when installed), Ctrl+V (only when no text field has the focus),
    the Paste or Add file icon of the next free slot. Each filled slot has a bar of icons: Remove, Cut out (BiRefNet in
    ComfyUI), Describe and (with a description) Copy text."""

    SLOT = 108         # px (before the display scaling): every slot is the same size, whatever the model
    ICON_PX = 24       # size of the slot icons (vector line icons, icons.py) before the display scaling: the ONE place to change it
    PER_ROW = 3        # slots per row
    BAR_ICONS = 4      # the most icons one bar holds (the slot is as tall as that needs)

    # ---- wrapped window methods ----
    def _on_mode_ui(self):
        super()._on_mode_ui()
        self._refs_update()

    def _request(self):
        req = super()._request()
        req.refs = self._refs_for(req.mode)     # the descriptions are already in the prompt field (Describe writes them there)
        return req

    # ---- state ----
    def _refs_model(self):
        m = self._model() if hasattr(self, "_model") else None
        return m if (m is not None and m.max_refs > 0) else None

    def _refs_wanted(self) -> bool:
        return self._refs_model() is not None and self.v_mode.get() == MULTI_MODE

    def _refs_for(self, run_mode: str) -> list:
        from .bridge import REF_MODES
        slots = getattr(self, "refslots", None)
        if slots is None or run_mode not in REF_MODES or not self._refs_wanted():
            return []
        return slots.images()

    # ---- build ----
    def _refs_ensure(self):
        if getattr(self, "f_refs", None) is not None:
            return
        import tkinter as tk
        from tkinter import ttk
        from .gui_common import Tooltip
        self.refslots = RefSlots()
        self._ref_photos: list = []
        self._ref_busy: set[int] = set()
        self._ref_job = None
        self.f_refs = ttk.Frame(self.f_body)      # inside the body frame (gui.py _build): it is packed before f_neg, which lives there
        head = ttk.Frame(self.f_refs)
        head.pack(fill="x")
        self.lbl_refs = ttk.Label(head, text="Reference images", style="Muted.TLabel")
        self.lbl_refs.pack(side="left")
        self.lbl_refmax = ttk.Label(head, text="", style="Muted.TLabel")      # always shown, on the line above the slots:
        self.lbl_refmax.pack(side="left", padx=(self._px(12), 0))           # "Reference images (1/3)   Max. images: 3"
        self.f_refgrid = ttk.Frame(self.f_refs)
        self.f_refgrid.pack(fill="x", pady=(4, 0))
        self.lbl_refnames = ttk.Label(self.f_refs, text="", style="Muted.TLabel", wraplength=self._px(380 - 24), justify="left")
        self.lbl_refnames.pack(fill="x", pady=(4, 0))
        self.lbl_refmsg = ttk.Label(self.f_refs, text="", style="Hint.TLabel", wraplength=self._px(380 - 24), justify="left")   # only packed while it has text
        self._refs_dnd = self._refs_setup_dnd()
        try:
            self.root.bind("<Control-v>", self._refs_ctrl_v, add="+")
            self.root.bind("<Control-V>", self._refs_ctrl_v, add="+")
        except tk.TclError:
            pass

    def _refs_setup_dnd(self) -> bool:
        """Drag and drop needs the optional package tkinterdnd2; without it everything else still works."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            TkinterDnD._require(self.root)
            self.f_refs.drop_target_register(DND_FILES)
            self.f_refs.dnd_bind("<<Drop>>", self._refs_on_drop)
            return True
        except Exception:
            return False

    # ---- show / hide / redraw ----
    def _refs_retag(self):
        """The model changed: the image names typed in the prompt get the new model's naming rule."""
        m = self._refs_model()
        if m is None or getattr(self, "_booting", False):
            return
        old = getattr(self, "_tag_style_seen", None)
        self._tag_style_seen = m.tag_style
        if not old or old == m.tag_style:
            return
        t = getattr(self, "t_prompt", None)
        if t is None or str(t.cget("state")) == "disabled":
            return
        cur = t.get("1.0", "end").rstrip("\n")
        new = retag(cur, old, m.tag_style)
        if new != cur:
            t.delete("1.0", "end")
            t.insert("1.0", new)

    def _refs_update(self):
        self._refs_retag()
        want = self._refs_wanted()
        if not want and getattr(self, "f_refs", None) is None:
            return
        self._refs_ensure()
        if not want:
            self.f_refs.pack_forget()
            return
        m = self._refs_model()
        self.refslots.set_model(m.max_refs, m.tag_style)
        self.f_refs.pack(fill="x", padx=10, pady=(6, 0), before=self.f_neg)
        self._refs_redraw()

    def _refs_redraw(self):
        import tkinter as tk
        from tkinter import ttk
        from .gui_common import ACCENT, FG, MUTED, PANEL, Tooltip
        for w in (self.f_refgrid.winfo_children() or []):
            w.destroy()
        self._refs_preview_close()   # the slots change: an open larger view may show a picture that is gone
        self._ref_photos = []
        rs = self.refslots
        s = self._px(self.SLOT)
        per_row = self.PER_ROW
        for c in range(per_row):
            self.f_refgrid.columnconfigure(c, minsize=s + self._px(6))
        n_used = len(rs.active)
        self.lbl_refs.configure(text=f"Reference images ({n_used}/{rs.max_refs})")
        for k in range(self._refs_visible()):
            cell = ttk.Frame(self.f_refgrid)
            cell.grid(row=k // per_row, column=k % per_row, sticky="n", padx=(0, self._px(6)), pady=(0, self._px(4)))
            box = tk.Frame(cell, width=s, height=self._px(max(self.SLOT, self.BAR_ICONS * (self._icon_px() + 3) + 2)), bg=PANEL, highlightthickness=1, highlightbackground="#5c5c5c")
            box.pack_propagate(False)
            box.pack()
            if k < len(rs.items):
                it = rs.items[k]
                photo = tk.PhotoImage(data=_b64(thumbnail_png(it.image, s - 4 - self._px(self._bar_px()))))
                self._ref_photos.append(photo)
                lbl = tk.Label(box, image=photo, bg=PANEL, bd=0)
                lbl.pack(expand=True, side="left")
                lbl.configure(cursor="hand2")
                lbl.bind("<Button-1>", lambda e, k=k: self._refs_preview(k))   # a larger view (500 %)
                if self._refs_dnd:      # a drop onto a filled slot replaces its picture (the rest of the frame adds)
                    self._refs_slot_drop(box, k)
                    self._refs_slot_drop(lbl, k)
                Tooltip(lbl, f"{it.name or 'clipboard'}" + ("  (cut out)" if it.cut_out else "") + (f"\n{it.description}" if it.description else ""))
                tag = rs.tag(k)
                ttk.Label(cell, text=tag or f"image {k + 2}", style="Hint.TLabel", anchor="center").pack(fill="x")      # centred under the slot
                if it.description:      # shown under the image; Describe also wrote it into the prompt field
                    ttk.Label(cell, text=it.description, style="Muted.TLabel", wraplength=s, justify="left").pack(anchor="w")
                busy = k in self._ref_busy
                bar = [("remove", "Remove", "Takes this image out of the slots.", lambda k=k: self._refs_remove(k), False),
                       ("cut", "Undo cut" if it.cut_out else "Cut out",
                        "Back to the original picture." if it.cut_out else "Removes the background (BiRefNet in ComfyUI).", lambda k=k: self._refs_cut(k), True),
                       ("describe", "Describe", "Qwen 3.5 9B writes a short description of this picture (about 5 s).", lambda k=k: self._refs_describe(k), True)]
                if it.description:
                    bar.append(("copy", "Copy text", "Puts the description on the clipboard.", lambda k=k: self._refs_copy_text(k), False))
                self._refs_bar(box, bar, busy)
            else:
                tk.Label(box, text="Drop a picture\nor Ctrl+V", fg=MUTED, bg=PANEL, bd=0,
                         justify="center").pack(expand=True, side="left")
                # the one empty slot takes the pictures: paste and add file sit in its bar
                self._refs_bar(box, [("paste", "Paste", "Takes the picture from the clipboard (Ctrl+V does the same when no text field has the focus).", self._refs_paste, False),
                                     ("file", "Add file", "Picks a picture file. Or drop files onto a slot.", self._refs_add_file, False)], False)
        over = len(rs.overflow)
        self.lbl_refmax.configure(text=f"Max. images: {rs.max_refs}")
        hint = rs.hint()
        self.lbl_refnames.configure(text=("Name them in your text: " + hint + "." if hint else
                                          "Add a picture, then name it in your text."))
        if over:
            self._refs_say(f"The last {over} image(s) are kept but not sent.")
        elif not self._refs_dnd and not getattr(self, "_ref_dnd_told", False):
            self._ref_dnd_told = True
            self._refs_say("Drag and drop needs the package tkinterdnd2: run setup-windows.bat again. Ctrl+V, Paste and Add file work without it.")
        try:
            self._on_content_size()
        except Exception:
            pass

    def _refs_visible(self) -> int:
        """How many slots are shown: the filled ones and exactly one empty slot ("Drop a picture or Ctrl+V") while the model
        takes more; no empty placeholders (the 380 px window grows a row at a time)."""
        rs = self.refslots
        return min(rs.max_refs, len(rs.items) + 1)

    def _icon_px(self) -> int:
        return self.ICON_PX

    def _bar_px(self) -> int:
        """Width of the icon bar inside a slot (before the display scaling)."""
        return self._icon_px() + 6

    def _refs_icon(self, kind: str, color: str):
        cache = self.__dict__.setdefault("_ref_icon_cache", {})
        if (kind, color) not in cache:
            from . import icons
            cache[(kind, color)] = icons.photo(self.root, kind, color, self._px(self.ICON_PX))   # drawn at the real pixel size
        return cache[(kind, color)]

    def _refs_bar(self, box, buttons, busy: bool):
        """The narrow icon bar at the right edge inside a slot: one icon per action, the old word as its tooltip; under the
        mouse an icon turns orange. `buttons`: (icon, word, explanation, command, waits) - an action that waits is greyed
        out while a job runs."""
        import tkinter as tk
        from .gui_common import ACCENT, DISABLED, FG, PANEL, Tooltip
        bar = tk.Frame(box, width=self._px(self._bar_px()), bg=PANEL, bd=0)
        bar.pack(side="right", fill="y")
        for kind, word, tip, cmd, waits in buttons:
            off = busy and waits
            lb = tk.Label(bar, image=self._refs_icon(kind, DISABLED if off else FG), bg=PANEL, bd=0, cursor="" if off else "hand2")
            lb.pack(pady=self._px(1))
            if not off:
                lb.bind("<Button-1>", lambda e, c=cmd: c())
                lb.bind("<Enter>", lambda e, l=lb, k=kind: l.configure(image=self._refs_icon(k, ACCENT)), add="+")
                lb.bind("<Leave>", lambda e, l=lb, k=kind: l.configure(image=self._refs_icon(k, FG)), add="+")
            Tooltip(lb, f"{word}: {tip}")

    def _refs_preview(self, k: int):
        """A click on a slot picture: a larger view (500 %, at most twice as wide as the plugin and as tall as it) in a borderless
        window beside the plugin. The X, Esc, a click on the picture or a click elsewhere closes it; a click on the same
        slot again too."""
        import tkinter as tk
        from .gui_common import ACCENT, FG, PANEL
        was = getattr(self, "_ref_preview", None)
        self._refs_preview_close()
        if was is not None and was[0] == k:
            return
        rs = self.refslots
        if k >= len(rs.items):
            return
        it = rs.items[k]
        root = self.root
        root.update_idletasks()
        win = (root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height())
        thumb = self._px(self.SLOT) - 4 - self._px(self._bar_px())
        w, h = preview_size(it.image.size, thumb, 2 * win[2], win[3])
        vx = root.winfo_vrootx()
        x, y = preview_position(win, (w, h), vx, vx + root.winfo_vrootwidth())
        top = tk.Toplevel(root)
        top.wm_overrideredirect(True)
        top.configure(bg=PANEL, highlightthickness=1, highlightbackground="#5c5c5c")
        top.wm_geometry(f"+{x}+{y}")
        im = flatten(it.image, (0x28, 0x28, 0x28)).resize((w, h), Image.LANCZOS)
        import io
        buf = io.BytesIO()
        im.save(buf, "PNG")
        photo = tk.PhotoImage(data=_b64(buf.getvalue()))
        pic = tk.Label(top, image=photo, bg=PANEL, bd=0)
        pic.image = photo
        pic.pack()
        close = tk.Label(top, image=self._refs_icon("remove", FG), bg=PANEL, bd=0, cursor="hand2")
        close.place(relx=1.0, x=-self._px(4), y=self._px(4), anchor="ne")
        close.bind("<Enter>", lambda e: close.configure(image=self._refs_icon("remove", ACCENT)))
        close.bind("<Leave>", lambda e: close.configure(image=self._refs_icon("remove", FG)))
        for wd in (close, pic):
            wd.bind("<Button-1>", lambda e: self._refs_preview_close())
        top.bind("<Escape>", lambda e: self._refs_preview_close())
        top.bind("<FocusOut>", lambda e: root.after(150, self._refs_preview_lost_focus))
        self._ref_preview = (k, top)
        top.focus_force()

    def _refs_preview_lost_focus(self):
        """A click elsewhere closes the larger view, except a click on the slot picture itself (that one toggles it)."""
        p = getattr(self, "_ref_preview", None)
        if p is None:
            return
        try:
            if p[1].focus_displayof() is not None:
                return
        except Exception:
            pass
        self._refs_preview_close()

    def _refs_preview_close(self):
        p = getattr(self, "_ref_preview", None)
        self._ref_preview = None
        if p is not None:
            try:
                p[1].destroy()
            except Exception:
                pass

    def _refs_copy_text(self, k: int):
        items = self.refslots.items
        if 0 <= k < len(items) and items[k].description:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(items[k].description)
                self._refs_say("Description copied.")
            except Exception:
                self._refs_say("The clipboard is not available.")

    def _refs_say(self, text: str):
        self.lbl_refmsg.configure(text=text)
        if text:
            self.lbl_refmsg.pack(fill="x")
        else:
            self.lbl_refmsg.pack_forget()           # no empty line between the slots and the negative prompt

    # ---- adding ----
    def _refs_add_image(self, image, name: str = ""):
        try:
            self.refslots.add(image, name)
            self._refs_say("")
        except RefError as e:
            self._refs_say(str(e))
        self._refs_redraw()

    def _refs_paste(self):
        im = clipboard.read_image()
        if im is None:
            self._refs_say("The clipboard holds no picture." if clipboard.available() else "Pasting from the clipboard works on Windows only.")
            return
        self._refs_add_image(im, "clipboard")

    def _refs_ctrl_v(self, event=None):
        """Ctrl+V adds a picture, but never takes the shortcut away from a text field (prompt, spin boxes ...)."""
        try:
            cls = str(self.root.focus_get().winfo_class())
        except Exception:
            cls = ""
        if cls in ("Text", "Entry", "TEntry", "TCombobox", "TSpinbox", "Spinbox") or not self._refs_wanted():
            return None
        im = clipboard.read_image()
        if im is None:
            return None
        self._refs_add_image(im, "clipboard")
        return "break"

    def _refs_add_file(self):
        from tkinter import filedialog
        paths = self._dialog(filedialog.askopenfilenames, title="Reference images", filetypes=[("Pictures", " ".join("*" + e for e in clipboard.IMAGE_SUFFIXES)), ("All files", "*.*")])
        self._refs_add_paths(self.root.tk.splitlist(paths) if isinstance(paths, str) else paths)

    def _refs_slot_drop(self, widget, k: int):
        try:
            from tkinterdnd2 import DND_FILES
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", lambda e, k=k: self._refs_on_drop(e, k))
        except Exception:
            pass

    def _refs_on_drop(self, event, at: int | None = None):
        """Files dropped onto the slots: added, or (onto filled slot `at`) the first one replaces that picture."""
        try:
            paths = [Path(p) for p in self.root.tk.splitlist(event.data)]
        except Exception:
            paths = parse_drop_data(str(getattr(event, "data", "")))
        self._refs_add_paths(paths, at)
        return getattr(event, "action", "copy")

    def _refs_add_paths(self, paths, at: int | None = None):
        if at is not None:
            self._ref_busy.discard(at)
        n, notes = self.refslots.add_files(paths, at)
        self._refs_say(notes[0] if notes else "")
        self._refs_redraw()

    # ---- one slot ----
    def _refs_remove(self, k: int):
        if k < len(self.refslots.items):
            self.refslots.remove(k)
        self._ref_busy.clear()
        self._refs_say("")
        self._refs_redraw()

    def _refs_cut(self, k: int):
        it = self.refslots.items[k]
        if it.cut_out:
            self.refslots.revert(k)
            self._refs_redraw()
            return
        import threading
        self._ref_busy.add(k)
        box: dict = {}
        src = it

        def work():
            try:
                box["image"] = self.bridge.remove_background(src.image)
            except Exception as e:   # ComfyUI not running, BiRefNet missing ...
                box["error"] = str(e)

        threading.Thread(target=work, daemon=True).start()
        self._refs_say("Cutting out the background …")
        self._refs_redraw()

        def check():
            if "image" not in box and "error" not in box:
                self.root.after(200, check)
                return
            self._ref_busy.discard(k)
            if "error" in box:
                self._refs_say("Cut out failed: " + box["error"])
            elif src in self.refslots.items:
                self.refslots.replace(self.refslots.items.index(src), box["image"])
                self._refs_say("")
            self._refs_redraw()
        self.root.after(200, check)

    def _refs_describe(self, k: int):
        """Qwen 3.5 9B describes the picture in the slot (ComfyUI, describe-image.json); the text is shown under the image and written
        into the prompt field as its own line ("<image2>: ..."), where it can be edited or deleted."""
        import threading
        src = self.refslots.items[k]
        if k in self._ref_busy:
            return
        self._ref_busy.add(k)
        box: dict = {}

        def work():
            try:
                box["text"] = self.bridge.describe_image(src.image)
            except Exception as e:   # ComfyUI not running, no text model ...
                box["error"] = str(e)

        threading.Thread(target=work, daemon=True).start()
        self._refs_say("Describing the picture \u2026")
        self._refs_redraw()

        def check():
            if "text" not in box and "error" not in box:
                self.root.after(200, check)
                return
            self._ref_busy.discard(k)
            if "error" in box:
                self._refs_say("Describe failed: " + box["error"])
            else:
                old, src.description = src.description, box["text"]
                i = self.refslots.items.index(src) if src in self.refslots.items else 0
                self._refs_say(f"{self.refslots.tag(i) or 'image'}: {box['text']}")
                t = getattr(self, "t_prompt", None)
                if t is not None and src in self.refslots.items and str(t.cget("state")) != "disabled":
                    cur = t.get("1.0", "end").rstrip("\n")
                    new = self.refslots.put_description(cur, i, old)
                    if new != cur:
                        t.delete("1.0", "end")
                        t.insert("1.0", new)
                    elif old:      # the old line was changed by hand: the prompt stays, the new text is under the image
                        self._refs_say("You changed the description line in the prompt, so it was kept. The new text is under the image (copy icon).")
            self._refs_redraw()
        self.root.after(200, check)

def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")
