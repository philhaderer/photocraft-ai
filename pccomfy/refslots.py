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
DEFAULT_BACKGROUND = (255, 255, 255)


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

    # ---- what the bridge sends ----

    def images(self) -> list[Image.Image]:
        return [it.image for it in self.active]
