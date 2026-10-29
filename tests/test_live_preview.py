"""Live preview (T3a, user 29.10.: 1A with TAESD files optional, 2B, 3A, 4A): ComfyUI's binary preview frames are read
from the websocket, the prompt asks for the preview method "taesd" only when the checkbox is on, the frame shows above the
status line while the run goes and disappears with "Done". The checkbox is on at every start and after Reset.

    python tests/test_live_preview.py
"""
import io
import json
import struct
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import comfy, inventory, manifest, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def jpeg(color=(10, 120, 240), size=(48, 32)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


def parse_checks():
    # event 1: image type + JPEG
    im = comfy.preview_image(struct.pack(">II", 1, 1) + jpeg())
    assert im is not None and im.size == (48, 32) and im.mode == "RGB"
    # event 4: metadata with the prompt id + image; a frame of another prompt is dropped
    meta = json.dumps({"prompt_id": "p1", "node_id": "3"}).encode()
    msg = struct.pack(">II", 4, len(meta)) + meta + jpeg()
    assert comfy.preview_image(msg, "p1").size == (48, 32)
    assert comfy.preview_image(msg, "other") is None
    # anything else: None, never an exception
    assert comfy.preview_image(b"") is None and comfy.preview_image(struct.pack(">II", 3, 0)) is None
    assert comfy.preview_image(struct.pack(">II", 1, 1) + b"broken") is None


class FakeWS:
    def __init__(self, msgs):
        self.msgs = list(msgs)

    def recv(self):
        return self.msgs.pop(0)

    def close(self):
        pass


def wait_checks():
    c = comfy.ComfyUI("http://x")
    sent = {}
    c._json = lambda path, payload=None: (sent.__setitem__(path, payload), {"prompt_id": "p1"})[1]
    c.queue({"1": {}}, preview="taesd")
    assert sent["/prompt"]["extra_data"] == {"preview_method": "taesd"}
    sent.clear()
    c.queue({"1": {}})
    assert "extra_data" not in sent["/prompt"]              # no preview asked for: ComfyUI's start setting

    msgs = [struct.pack(">II", 1, 1) + jpeg(), json.dumps({"type": "progress", "data": {"prompt_id": "p1", "value": 1, "max": 4}}),
            struct.pack(">II", 1, 1) + jpeg((200, 0, 0)), json.dumps({"type": "execution_success", "data": {"prompt_id": "p1"}})]
    orig = comfy.websocket
    comfy.websocket = type("W", (), {"create_connection": staticmethod(lambda *a, **k: FakeWS(msgs)),
                                      "WebSocketTimeoutException": TimeoutError})
    try:
        c.history = lambda pid: {"status": {"completed": True, "status_str": "success"}}
        frames = []
        c.wait("p1", on_preview=frames.append)
        assert len(frames) == 2 and frames[1].getpixel((5, 5))[0] > 150
        msgs[:] = [struct.pack(">II", 1, 1) + jpeg(), json.dumps({"type": "execution_success", "data": {"prompt_id": "p1"}})]
        c.wait("p1")                                       # without a callback the frames are just skipped
    finally:
        comfy.websocket = orig


def bridge_checks():
    for on in (True, False):
        pc, _, b = T.make(tempfile.mkdtemp())
        b.comfy = T.FakeComfy()
        got = []
        b.on_preview = got.append
        req = Request(mode="edit", workflow=str(ROOT / "workflows" / "fibo2-edit.json"), enhance=False, preview=on)
        req.params = workflows.GenParams(prompt="make it night", seed=7)
        b.run(req)
        assert b.comfy.previews == (["taesd"] if on else [None]), b.comfy.previews
        assert len(got) == (1 if on else 0)


def gui_checks():
    import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
    gui = t.gui
    app = gui.App(t.cfgmod.load())
    assert app.v_live.get() is True                        # on at every start
    assert app._request().preview is True
    app.v_live.set(False)
    assert app._request().preview is False
    app.v_live.set(True)

    packed = []
    app.f_preview.winfo_manager = lambda: "pack" if packed else ""
    app.f_preview.pack = lambda *a, **k: packed.append(k)
    app.f_preview.pack_forget = lambda: packed.clear()
    gui_run = sys.modules["pccomfy.gui_run"]
    gui_run.icons.photo = lambda root, kind, color, px, image=None: ("photo", image.size)
    app.events.put(("preview", Image.new("RGB", (512, 512))))
    app.events.put(("preview", Image.new("RGB", (512, 256))))   # two in one round: only the newest is drawn
    app._poll()
    assert packed and packed[0].get("before") is app.f_status
    w = max(420, app._px(gui.MIN_W)) - app._px(20)
    assert app._preview_photo == ("photo", (w, w // 2)), app._preview_photo      # as wide as the window
    app.events.put(("done", "Done · seed 1 · created 1 layer · 3 s"))
    app._poll()
    assert not packed and app._preview_photo is None        # gone with the result

    app._minimized = True                                   # minimised: no preview
    app._show_preview(Image.new("RGB", (64, 64)))
    assert not packed
    app._minimized = False


def manifest_checks():
    """The TAESD files are optional and linked in the gear window (user 29.10.: default coarse colours, the files to test)."""
    want = {"flux3": "taef2_decoder.pth", "flux2": "taef2_decoder.pth", "fibo": "taef2_decoder.pth", "moss": "taef2_decoder.pth",
            "qwen": "taeqi2_1_decoder.pth", "krea2": "lighttaew2_1.safetensors"}
    for key, name in want.items():
        assert name in manifest.TABS[key].optional and name not in manifest.tab_required(key), key
        f = manifest.FILES[name]
        assert f.kind == "preview" and f.target == r"models\vae_approx" and f.url.startswith("https://") and f.size
    inv = inventory.Inventory({"preview": ["taef2_decoder.safetensors"]})
    assert inv.has("taef2_decoder.pth") and not inv.has("taeqi2_1_decoder.pth")        # either file format counts
    assert "taeqi2_1_decoder.pth" in [f.name for f in inv.missing(manifest.TABS["qwen"].optional)]   # a note, never a block


def main():
    manifest_checks()
    parse_checks()
    wait_checks()
    bridge_checks()
    gui_checks()
    print("test_live_preview: ok")


if __name__ == "__main__":
    main()
