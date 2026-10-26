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

    def add_file(self, path) -> int:
        p = Path(path)
        if p.suffix.lower() not in clipboard.IMAGE_SUFFIXES or not p.is_file():
            raise RefError(f"{p.name}: not a picture file.")
        with Image.open(p) as im:
            im.load()
            return self.add(im, p.name)

    def add_files(self, paths) -> tuple[int, list[str]]:
        """Drop of several files: as many as fit. Returns (how many were added, messages for the ones that were not)."""
        n, notes = 0, []
        for p in paths:
            try:
                self.add_file(p)
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
        """A changed picture (pen, cut-out); the first version is kept for `revert`."""
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
        """The typed text plus the descriptions at its end, one per line. This is the prompt that is sent (see docs/prompt-aufbau.md)."""
        lines = self.description_lines()
        if not lines:
            return text
        return (text.rstrip() + "\n" if text.strip() else "") + "\n".join(lines)

    # ---- what the bridge sends ----

    def images(self) -> list[Image.Image]:
        return [it.image for it in self.active]


# ======================================================================================================================
# Pure helpers for the widget (tested without Tk)
# ======================================================================================================================

def apply_strokes(image: Image.Image, strokes: list, scale: float = 1.0) -> Image.Image:
    """The pen: draws `strokes` ([(colour, width, [(x, y), ...]), ...], in the preview's pixels) onto a copy of the image;
    `scale` = image pixels per preview pixel. Round line ends, one dot for a click."""
    from PIL import ImageDraw
    out = image.convert("RGBA")
    d = ImageDraw.Draw(out)
    for colour, width, pts in strokes:
        w = max(1, round(width * scale))
        pts = [(x * scale, y * scale) for x, y in pts]
        if len(pts) == 1:
            x, y = pts[0]
            d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=colour)
            continue
        d.line(pts, fill=colour, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=colour)
    return out


def thumbnail_png(image: Image.Image, size: int, background=(0x40, 0x40, 0x40)) -> bytes:
    """A PNG of the picture that fits into a size x size square (kept proportional), transparency shown on `background`."""
    import io
    t = flatten(image, background)
    t.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    t.save(buf, "PNG")
    return buf.getvalue()


PEN_COLOURS = ("#ff2a2a", "#2ad14b", "#2a7bff", "#ffd400", "#000000", "#ffffff")


# ======================================================================================================================
# The window part (Tk): one hook in gui.py puts RefSlotsMixin in front of the window's other mixins
# ======================================================================================================================

MULTI_MODE = "multi_edit"     # the window mode that shows the slots (it runs as a whole-image edit)


class RefSlotsMixin:
    """The reference slots of the window. Built the first time the window shows them (`_refs_ensure`), so the hook in gui.py
    is only the class line: `_on_mode_ui` (called on every tab / mode change) and `_request` are wrapped here.
    A slot takes a picture by drag and drop (tkinterdnd2, when installed), Ctrl+V (only when no text field has the focus),
    the Paste or Add file icon of the next free slot. Each filled slot has a bar of icons: Remove, Pen, Cut out (BiRefNet in
    ComfyUI), Describe and (with a description) Copy text."""

    SLOT = 108         # px (before the display scaling): every slot is the same size, whatever the model
    ICON_SCALE = 1.7   # the slot icons are the 16 px pixel art times this (the ONE place to make them bigger or smaller)
    BAR_ICONS = 5      # the most icons one bar holds (the slot is as tall as that needs)

    # ---- wrapped window methods ----
    def _on_mode_ui(self):
        super()._on_mode_ui()
        self._refs_update()

    def _request(self):
        req = super()._request()
        req.refs = self._refs_for(req.mode)
        if req.refs:        # the descriptions of the images that go along are added at the end of the prompt
            req.params.prompt = self.refslots.prompt_with_descriptions(req.params.prompt)
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
        self.f_refs = ttk.Frame(self.root)
        head = ttk.Frame(self.f_refs)
        head.pack(fill="x")
        self.lbl_refs = ttk.Label(head, text="Reference images", style="Muted.TLabel")
        self.lbl_refs.pack(side="left")
        self.f_refgrid = ttk.Frame(self.f_refs)
        self.f_refgrid.pack(fill="x", pady=(4, 0))
        self.lbl_refnames = ttk.Label(self.f_refs, text="", style="Muted.TLabel", wraplength=self._px(380 - 24), justify="left")
        self.lbl_refnames.pack(fill="x", pady=(4, 0))
        self.lbl_refmsg = ttk.Label(self.f_refs, text="", style="Hint.TLabel", wraplength=self._px(380 - 24), justify="left")
        self.lbl_refmsg.pack(fill="x")
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
    def _refs_update(self):
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
        self._ref_photos = []
        rs = self.refslots
        s = self._px(self.SLOT)
        for c in range(max(1, rs.max_refs)):
            self.f_refgrid.columnconfigure(c, minsize=s + self._px(6))
        n_used = len(rs.active)
        self.lbl_refs.configure(text=f"Reference images ({n_used}/{rs.max_refs})")
        for k in range(rs.max_refs):
            cell = ttk.Frame(self.f_refgrid)
            cell.grid(row=0, column=k, sticky="n", padx=(0, self._px(6)))
            box = tk.Frame(cell, width=s, height=self._px(max(self.SLOT, self.BAR_ICONS * (self._icon_px() + 3) + 2)), bg=PANEL, highlightthickness=1, highlightbackground="#5c5c5c")
            box.pack_propagate(False)
            box.pack()
            if k < len(rs.items):
                it = rs.items[k]
                photo = tk.PhotoImage(data=_b64(thumbnail_png(it.image, s - 4 - self._px(self._bar_px()))))
                self._ref_photos.append(photo)
                lbl = tk.Label(box, image=photo, bg=PANEL, bd=0)
                lbl.pack(expand=True, side="left")
                Tooltip(lbl, f"{it.name or 'clipboard'}" + ("  (cut out)" if it.cut_out else "") + (f"\n{it.description}" if it.description else ""))
                tag = rs.tag(k)
                ttk.Label(cell, text=tag or f"image {k + 2}", style="Hint.TLabel").pack(anchor="w")
                if it.description:      # shown under the image; it is also added to the end of the prompt
                    ttk.Label(cell, text=it.description, style="Muted.TLabel", wraplength=s, justify="left").pack(anchor="w")
                busy = k in self._ref_busy
                bar = [("remove", "Remove", "Takes this image out of the slots.", lambda k=k: self._refs_remove(k), False),
                       ("pen", "Pen", "Draw on the image (a circle around the part that counts).", lambda k=k: self._refs_pen(k), False),
                       ("cut", "Undo cut" if it.cut_out else "Cut out",
                        "Back to the original picture." if it.cut_out else "Removes the background (BiRefNet in ComfyUI).", lambda k=k: self._refs_cut(k), True),
                       ("describe", "Describe", "Qwen 3.5 9B writes a short description of this picture (about 5 s).", lambda k=k: self._refs_describe(k), True)]
                if it.description:
                    bar.append(("copy", "Copy text", "Puts the description on the clipboard.", lambda k=k: self._refs_copy_text(k), False))
                self._refs_bar(box, bar, busy)
            else:
                tk.Label(box, text="Drop a picture\nor Ctrl+V" if k == len(rs.items) else "free", fg=MUTED, bg=PANEL, bd=0,
                         justify="center").pack(expand=True, side="left")
                if k == len(rs.items):      # the next free slot takes the pictures: paste and add file sit in its bar
                    self._refs_bar(box, [("paste", "Paste", "Takes the picture from the clipboard (Ctrl+V does the same when no text field has the focus).", self._refs_paste, False),
                                         ("file", "Add file", "Picks a picture file. Or drop files onto a slot.", self._refs_add_file, False)], False)
                ttk.Label(cell, text="", style="Muted.TLabel").pack(anchor="w")
        over = len(rs.overflow)
        hint = rs.hint()
        self.lbl_refnames.configure(text=("Name them in your text: " + hint + "." if hint else
                                          "Add a picture, then name it in your text."))
        if over:
            self._refs_say(f"This model takes {rs.max_refs}: the last {over} image(s) are kept but not sent.")
        elif not self._refs_dnd and not getattr(self, "_ref_dnd_told", False):
            self._ref_dnd_told = True
            self._refs_say("Drag and drop needs the package tkinterdnd2: run setup-windows.bat again. Ctrl+V, Paste and Add file work without it.")
        try:
            self._on_content_size()
        except Exception:
            pass

    def _icon_px(self) -> int:
        return int(16 * round(self.ICON_SCALE * 10) / 10)

    def _bar_px(self) -> int:
        """Width of the icon bar inside a slot (before the display scaling)."""
        return self._icon_px() + 6

    def _refs_icon(self, kind: str, color: str):
        cache = self.__dict__.setdefault("_ref_icon_cache", {})
        if (kind, color) not in cache:
            from .gui_common import icon_image
            img = icon_image(self.root, kind, color)
            try:
                img = img.zoom(round(self.ICON_SCALE * 10)).subsample(10)     # 16 px -> 27 px at 1.7
            except Exception:
                pass
            cache[(kind, color)] = img
        return cache[(kind, color)]

    def _refs_bar(self, box, buttons, busy: bool):
        """The narrow icon bar at the right edge inside a slot: one 16 px icon per action, the old word as its tooltip.
        `buttons`: (icon, word, explanation, command, waits) - an action that waits is greyed out while a job runs."""
        import tkinter as tk
        from .gui_common import DISABLED, FG, PANEL, Tooltip
        bar = tk.Frame(box, width=self._px(self._bar_px()), bg=PANEL, bd=0)
        bar.pack(side="right", fill="y")
        for kind, word, tip, cmd, waits in buttons:
            off = busy and waits
            lb = tk.Label(bar, image=self._refs_icon(kind, DISABLED if off else FG), bg=PANEL, bd=0, cursor="" if off else "hand2")
            lb.pack(pady=self._px(1))
            if not off:
                lb.bind("<Button-1>", lambda e, c=cmd: c())
            Tooltip(lb, f"{word}: {tip}")

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
        paths = filedialog.askopenfilenames(title="Reference images", filetypes=[("Pictures", " ".join("*" + e for e in clipboard.IMAGE_SUFFIXES)), ("All files", "*.*")])
        self._refs_add_paths(self.root.tk.splitlist(paths) if isinstance(paths, str) else paths)

    def _refs_on_drop(self, event):
        try:
            paths = [Path(p) for p in self.root.tk.splitlist(event.data)]
        except Exception:
            paths = parse_drop_data(str(getattr(event, "data", "")))
        self._refs_add_paths(paths)
        return getattr(event, "action", "copy")

    def _refs_add_paths(self, paths):
        n, notes = self.refslots.add_files(paths)
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
        """Qwen 3.5 9B describes the picture in the slot (ComfyUI, describe-image.json); the text is shown under the image and added to
        the end of the prompt automatically."""
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
                src.description = box["text"]
                i = self.refslots.items.index(src) if src in self.refslots.items else 0
                self._refs_say(f"{self.refslots.tag(i) or 'image'}: {box['text']}")
            self._refs_redraw()
        self.root.after(200, check)

    def _refs_pen(self, k: int):
        import tkinter as tk
        from tkinter import ttk
        from .gui_common import ACCENT, BG, PANEL
        it = self.refslots.items[k]
        base = it.image.convert("RGBA")
        view = min(1.0, 520 / max(base.size))
        vw, vh = max(1, round(base.width * view)), max(1, round(base.height * view))
        top = tk.Toplevel(self.root)
        top.title("Pen")
        top.configure(bg=BG)
        top.transient(self.root)
        cv = tk.Canvas(top, width=vw, height=vh, bg=PANEL, highlightthickness=0, cursor="crosshair")
        cv.pack(padx=8, pady=8)
        bg_photo = tk.PhotoImage(data=_b64(thumbnail_png(base, max(vw, vh))))
        cv.create_image(0, 0, image=bg_photo, anchor="nw")
        state = {"colour": PEN_COLOURS[0], "strokes": [], "cur": None}
        v_w = tk.IntVar(value=6)

        def down(e):
            state["cur"] = [state["colour"], int(v_w.get()), [(e.x, e.y)]]
            state["strokes"].append(state["cur"])
            cv.create_oval(e.x - v_w.get() / 2, e.y - v_w.get() / 2, e.x + v_w.get() / 2, e.y + v_w.get() / 2,
                           fill=state["colour"], outline="", tags="pen")

        def move(e):
            c = state["cur"]
            if c is None:
                return
            x0, y0 = c[2][-1]
            c[2].append((e.x, e.y))
            cv.create_line(x0, y0, e.x, e.y, fill=c[0], width=c[1], capstyle="round", tags="pen")

        def up(_e):
            state["cur"] = None

        def undo():
            if state["strokes"]:
                state["strokes"].pop()
                cv.delete("pen")
                for colour, w, pts in state["strokes"]:
                    if len(pts) == 1:
                        x, y = pts[0]
                        cv.create_oval(x - w / 2, y - w / 2, x + w / 2, y + w / 2, fill=colour, outline="", tags="pen")
                    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                        cv.create_line(xa, ya, xb, yb, fill=colour, width=w, capstyle="round", tags="pen")

        def apply():
            if state["strokes"]:
                done = apply_strokes(base, [(c, w, p) for c, w, p in state["strokes"]], 1.0 / view)
                self.refslots.replace(k, done)
            top.destroy()
            self._refs_redraw()

        cv.bind("<ButtonPress-1>", down)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", up)
        bar = ttk.Frame(top)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        for c in PEN_COLOURS:
            sw = tk.Label(bar, width=2, bg=c, bd=1, relief="solid", cursor="hand2")
            sw.pack(side="left", padx=2)
            sw.bind("<Button-1>", lambda e, c=c: state.update(colour=c))
        ttk.Label(bar, text="Size", style="Muted.TLabel").pack(side="left", padx=(10, 2))
        ttk.Spinbox(bar, textvariable=v_w, from_=1, to=60, width=4).pack(side="left")
        ttk.Button(bar, text="Undo", style="Link.TButton", command=undo).pack(side="left", padx=10)
        ttk.Button(bar, text="Cancel", command=top.destroy).pack(side="right")
        ttk.Button(bar, text="Apply", command=apply).pack(side="right", padx=6)
        top._keep = bg_photo   # (Tk drops a picture nobody refers to)


def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")
