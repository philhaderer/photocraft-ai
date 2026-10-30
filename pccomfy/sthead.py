"""Reads the header of a ``.safetensors`` file, to recognise a renamed file ("looks like ...") in the chain list of the settings window.

Only the header is read: 8 bytes (its length) and the JSON with the tensor list (name, dtype, shape, byte range). The weights are never
loaded. Pickle files (.ckpt, .pt) are never opened. A file that is no valid safetensors file gives ``None``.
"""
from __future__ import annotations

import json
import os
import struct
from pathlib import Path

MAX_HEADER = 64 * 1024 * 1024        # the real headers are some 100 kB; anything bigger is not a safetensors file we want to parse


def read_header(path: str | Path) -> dict | None:
    """The tensor table of a ``.safetensors`` file ({tensor name: {dtype, shape, data_offsets}}, without ``__metadata__``), or None
    when the file is not a valid safetensors file or cannot be read."""
    p = Path(path)
    if p.suffix.lower() != ".safetensors":
        return None
    try:
        with open(p, "rb") as fh:
            raw = fh.read(8)
            if len(raw) != 8:
                return None
            n = struct.unpack("<Q", raw)[0]
            if not 2 <= n <= MAX_HEADER or 8 + n > os.fstat(fh.fileno()).st_size:
                return None
            head = json.loads(fh.read(n).decode("utf-8"))
    except (OSError, ValueError, struct.error):
        return None
    if not isinstance(head, dict):
        return None
    head.pop("__metadata__", None)
    if not all(isinstance(v, dict) and {"dtype", "shape", "data_offsets"} <= set(v) for v in head.values()):
        return None
    return head


def expected_size(head: dict) -> int:
    """The end of the data the header lists (the last tensor's end offset). The file holds 8 + header length + this many bytes
    at least (see ``is_complete``)."""
    return max((v["data_offsets"][1] for v in head.values()), default=0)


def is_complete(path: str | Path) -> bool:
    """True when the file holds at least the bytes its header lists (a half-finished download does not)."""
    head = read_header(path)
    if head is None:
        return False
    try:
        with open(path, "rb") as fh:
            n = struct.unpack("<Q", fh.read(8))[0]
        return os.path.getsize(path) >= 8 + n + expected_size(head)
    except OSError:
        return False


def dtypes(head: dict) -> set[str]:
    """The data types in the file (``{"BF16"}``, ``{"I8", "F32"}`` ...)."""
    return {v["dtype"] for v in head.values()}
