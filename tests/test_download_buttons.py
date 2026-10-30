"""The download symbols of the settings window and the ComfyUI folder finder, against the stubbed Tk (no network, no GPU).

    python tests/test_download_buttons.py
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_settings_ui as ts  # noqa: E402  (installs the Tk stub)

t, td = ts.t, ts.td
from pccomfy import comfydir, downloads, inventory, manifest, ui_downloads  # noqa: E402

gui = t.gui
NODES = ts.NODES
SMALL = "taef2_decoder.pth"                       # Hugging Face, not gated
GATED = "flux3-image-klein-int8-convrot.safetensors"


def drain(app, until=lambda: False, limit=200):
    """Take the "download" events the worker sent and hand them to the window, until ``until()`` or no more come."""
    for _ in range(limit):
        if until():
            return
        try:
            kind, data = app.events.get(timeout=5)
        except Exception:
            return
        if kind == "download":
            app._download_event(data)


def main():
    # ---- the ComfyUI folder finder
    base = Path(tempfile.mkdtemp())
    root = base / "ComfyUI"
    (root / "models").mkdir(parents=True)
    (root / "main.py").write_text("", encoding="utf-8")
    (base / "python_embeded").mkdir()
    assert comfydir.models_dir_of(root) == root / "models" and comfydir.models_dir_of(root / "models") == root / "models"
    assert comfydir.models_dir_of(base) == root / "models" and comfydir.models_dir_of(base / "nothing") is None
    assert comfydir.root_from_process(str(base / "python_embeded" / "python.exe"), r".\python_embeded\python.exe  ComfyUI\main.py") == root
    assert comfydir.root_from_process(r"C:\Python\python.exe", f'python "{root / "main.py"}" --port 8188') == root
    assert comfydir.root_from_process(r"C:\nowhere\python.exe", "python x.py") is None
    assert comfydir.find_root("http://example.org:8188") is None                   # only a local server is looked up

    # ---- the buttons
    mdir = Path(tempfile.mkdtemp())
    os.environ["PCCOMFY_MODELS_DIR"] = str(mdir)
    app = ts.make_app()
    lists = td.full_lists()
    lists["preview"] = []
    lists["vae"].remove("flux2-vae_small.safetensors")
    lists["unet"].remove("moss_image_sft_int8_convrot.safetensors")
    lists["vae"].remove("flux2-vae.safetensors")
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(lists, NODES)})
    app.open_settings()
    files = {d["name"]: d for d in ts.file_rows(app)}
    assert files[SMALL]["dl"] is None and files[SMALL]["browser"] is False and files[GATED]["browser"] is True
    heads = {r[1]: r[5] for r in app._settings_rows() if r[0] == "model"}
    assert heads["moss"]["count"] == 2 and heads["moss"]["size"] and heads["krea2"] is None      # the all-missing symbol: two or more

    fake_gate = threading.Event()
    log = []

    def fake_download(url, dest, size=0, sha256="", progress=None, cancel=None, **kw):
        log.append(Path(dest).name)
        progress(10, size or 100, "downloading")
        fake_gate.wait(10)
        if cancel is not None and cancel():
            raise downloads.Cancelled("Cancelled.")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"x")
        progress(size or 100, size or 100, "verifying")
        return Path(dest)

    real, ui_downloads.downloads.download = ui_downloads.downloads.download, fake_download
    opened = []
    ui_downloads.webbrowser.open = lambda u: opened.append(u)
    try:
        # a refused OK starts nothing
        t.mb.askokcancel = lambda *a, **k: False
        app.download_file(SMALL)
        assert app._dl == {} and log == []
        t.mb.askokcancel = lambda *a, **k: True

        # a gated file opens its page; nothing is loaded
        app.download_file(GATED)
        assert opened == [manifest.FILES[GATED].url] and app._dl == {}

        # one file: queued at once, shown as loading, the target is the sub-folder of its kind
        app.download_file(SMALL)
        assert app._dl_order == [SMALL] and app._dl[SMALL]["target"] == mdir / "vae_approx" / SMALL
        drain(app, until=lambda: app._dl[SMALL]["done"] > 0)
        info = app._dl_info(SMALL)
        assert info["state"] == "loading" and info["done"] == 10
        assert [d for d in ts.file_rows(app) if d["name"] == SMALL][0]["dl"]["state"] == "loading"
        fake_gate.set()
        drain(app, until=lambda: SMALL not in app._dl)
        assert (mdir / "vae_approx" / SMALL).read_bytes() == b"x" and SMALL in app._dl_restart
        assert "restart ComfyUI" in app.v_status.get()
        assert [d for d in ts.file_rows(app) if d["name"] == SMALL][0]["restart"] is True
        app.download_file(SMALL)                                                    # it is there now: nothing again
        assert app._dl == {} and "already in" in app.v_status.get()

        # all missing of a model: queued one after the other; a queued one can be taken out, the running one stopped
        fake_gate.clear()
        log.clear()
        missing = [f.name for f, found, _lv in next(r for r in app.inv.rows() if r["key"] == "moss")["files"]
                   if found is None and f.url and not ui_downloads.browser_only(f)]
        assert len(missing) >= 2, missing
        app.download_missing("moss")
        assert app._dl_order == missing
        drain(app, until=lambda: app._dl[missing[0]]["done"] > 0)
        assert app._dl_info(missing[0])["state"] == "loading" and app._dl_info(missing[1])["state"] == "queued"
        app.download_cancel(missing[1])
        assert missing[1] not in app._dl and app._dl_order == [missing[0]]
        app.download_cancel(missing[0])
        fake_gate.set()
        drain(app, until=lambda: not app._dl)
        assert app._dl == {} and not (mdir / "vae" / missing[0]).exists() and "Cancelled" in app.v_status.get()
    finally:
        ui_downloads.downloads.download = real
        del os.environ["PCCOMFY_MODELS_DIR"]
    app._settings_close()
    print("ok")


if __name__ == "__main__":
    main()
