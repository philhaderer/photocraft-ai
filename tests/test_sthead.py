"""Reading the .safetensors header (pccomfy/sthead.py) and the "looks like ..." hints in the chain list of the settings window.

    python tests/test_sthead.py
"""
import json
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402,F401  (installs the Tk stub and a temporary PCCOMFY_HOME)
from pccomfy import manifest, sthead, ui_settings  # noqa: E402


def make(path: Path, tensors: dict, pad: int = 0, cut: int = 0) -> Path:
    """A safetensors file with the given tensors ({name: (dtype, shape, nbytes)}); ``pad`` adds data bytes up to a total size,
    ``cut`` removes bytes from the end (a half download)."""
    head, off = {}, 0
    for k, (dt, shape, n) in tensors.items():
        head[k] = {"dtype": dt, "shape": shape, "data_offsets": [off, off + n]}
        off += n
    raw = json.dumps({"__metadata__": {"format": "pt"}, **head}).encode()
    data = struct.pack("<Q", len(raw)) + raw + b"\0" * (off + pad)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data[:len(data) - cut] if cut else data)
    return path


class Stub(ui_settings.SettingsMixin):
    def __init__(self, base):
        self.base = base

    def models_dir(self, ask=True):
        return self.base


def main():
    tmp = Path(tempfile.mkdtemp(prefix="sthead-"))
    ok = make(tmp / "a.safetensors", {"w": ("I8", [4, 4], 16), "b": ("F32", [4], 16)})
    h = sthead.read_header(ok)
    assert set(h) == {"w", "b"} and sthead.dtypes(h) == {"I8", "F32"} and sthead.is_complete(ok)
    assert not sthead.is_complete(make(tmp / "cut.safetensors", {"w": ("I8", [4], 4)}, cut=2))
    assert sthead.read_header(tmp / "missing.safetensors") is None
    (tmp / "x.ckpt").write_bytes(b"\x80\x04pickle")
    assert sthead.read_header(tmp / "x.ckpt") is None            # no pickle files, whatever they hold
    (tmp / "junk.safetensors").write_bytes(b"not a safetensors file at all")
    assert sthead.read_header(tmp / "junk.safetensors") is None
    (tmp / "huge.safetensors").write_bytes(struct.pack("<Q", 2 ** 40) + b"{}")
    assert sthead.read_header(tmp / "huge.safetensors") is None  # a header length that does not fit the file
    (tmp / "short.safetensors").write_bytes(b"\x01\x02")
    assert sthead.read_header(tmp / "short.safetensors") is None

    # the hints: a renamed copy of a manifest file (same size, valid header) says what it looks like. A small made-up manifest entry
    # keeps the test files tiny.
    base = tmp / "models"
    tensors = {"w": ("F16", [2], 4)}
    size = make(base / "vae" / "renamed.safetensors", tensors).stat().st_size
    real = manifest.File("test-vae.safetensors", "vae", size=size)
    manifest.FILES[real.name] = real
    make(base / "vae" / "samesize-junk.safetensors", {"w": ("F16", [2], 4)}, pad=3)      # another size: no hint
    st = Stub(base)
    hints = st._link_hints(real.name, ["renamed.safetensors", "samesize-junk.safetensors", "ghost.safetensors"])
    assert hints == {"renamed.safetensors": "looks like " + real.name}, hints
    assert "ghost.safetensors" not in hints                     # a file that is not in the models folder: no hint

    # a half-finished copy says so
    make(base / "vae" / "half.safetensors", {"w": ("F16", [2], 4)}, cut=2)
    assert st._link_hints(real.name, ["half.safetensors"]) == {"half.safetensors": "incomplete?"}
    # no models folder known (ask=False): no hints, no crash
    assert Stub(None)._link_hints(real.name, ["renamed.safetensors"]) == {}
    assert st._link_hints("no-such-file", ["x"]) == {}
    del manifest.FILES[real.name]
    print("ok")


if __name__ == "__main__":
    main()
