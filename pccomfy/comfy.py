"""Minimal ComfyUI API client (standard library + Pillow only).

Endpoints used:
  GET  /system_stats, /object_info/<Node>   – connection check, model/sampler lists
  POST /upload/image                         – upload image and mask (land in input/)
  POST /prompt                               – queue an API-format graph
  WS   /ws?clientId=…                        – progress and live preview frames (optional, needs websocket-client)
  GET  /history/<prompt_id>, /view           – fetch results
  POST /interrupt, /queue                    – cancel
"""

from __future__ import annotations

import http.client
import io
import json
import struct
import threading
import time
import uuid
import urllib.parse
from typing import Callable

from PIL import Image

try:  # `websocket-client` package (Arch: python-websocket-client) – only for the progress bar
    import websocket  # type: ignore
except Exception:  # pragma: no cover
    websocket = None


class ComfyError(RuntimeError):
    pass


class Cancelled(Exception):
    pass


PREVIEW_IMAGE, PREVIEW_IMAGE_WITH_METADATA = 1, 4      # ComfyUI's binary websocket events (protocol.py BinaryEventTypes)


def preview_image(data: bytes, prompt_id: str | None = None) -> Image.Image | None:
    """A live preview frame from a binary websocket message: event 1 = image type (1 JPEG, 2 PNG) + image; event 4 =
    length + JSON metadata (with the prompt id) + image. None for anything else or a frame of another prompt."""
    try:
        if len(data) < 8:
            return None
        event, head = struct.unpack(">II", data[:8])
        if event == PREVIEW_IMAGE:
            body = data[8:]
        elif event == PREVIEW_IMAGE_WITH_METADATA:
            meta = json.loads(data[8:8 + head].decode("utf-8"))
            if prompt_id and meta.get("prompt_id") not in (None, prompt_id):
                return None
            body = data[8 + head:]
        else:
            return None
        im = Image.open(io.BytesIO(body))
        im.load()
        return im.convert("RGB")
    except Exception:
        return None


class ComfyUI:
    def __init__(self, url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.timeout = timeout
        parts = urllib.parse.urlsplit(self.url)
        self._host, self._port = parts.hostname or "127.0.0.1", parts.port or 80
        self._local = threading.local()
        self._cache: dict = {}
        self._cache_lock = threading.RLock()
        self.client_id = uuid.uuid4().hex
        self.name_fixer: Callable[[dict], object] | None = None   # called with every graph before it is queued (see inventory.apply_names)

    # ---------- HTTP ----------

    # Lists that rarely change are read at most once per CACHE_SECONDS (start, "Refresh", opening the settings window and a
    # download each ask for them; fired together they were 16 connections within a second, 30.10.). GETs share one
    # keep-alive connection per thread; a POST gets a connection of its own (a stale one must never send a job twice).
    CACHE_SECONDS = 10.0
    _CACHED = ("/system_stats", "/object_info", "/models/")

    def invalidate(self) -> None:
        """Forget the cached lists (a file was just added)."""
        with self._cache_lock:
            self._cache.clear()

    def _connection(self, fresh: bool) -> http.client.HTTPConnection:
        if fresh:
            return http.client.HTTPConnection(self._host, self._port, timeout=self.timeout)
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._local.conn = http.client.HTTPConnection(self._host, self._port, timeout=self.timeout)
        return conn

    def _request(self, path: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None):
        method = method or ("POST" if data is not None else "GET")
        fresh = method != "GET"
        for attempt in (0, 1):
            conn = self._connection(fresh)
            reused = not fresh and getattr(conn, "sock", None) is not None
            try:
                conn.request(method, path, body=data, headers=headers or {})
                r = conn.getresponse()
                body, status = r.read(), r.status
                break
            except (http.client.HTTPException, OSError) as e:
                conn.close()
                if not fresh:
                    self._local.conn = None
                if reused and attempt == 0:       # the server closed an idle connection: once more on a new one (GET only)
                    continue
                reason = getattr(e, "strerror", None) or e
                raise ComfyError(f"No connection to ComfyUI at {self.url} ({reason}). Is the server running?") from None
            finally:
                if fresh:
                    conn.close()
        if status >= 400:
            raise ComfyError(self._explain(status, body.decode(errors="replace")))
        return body

    def _json(self, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"} if data else {}
        if data is None and path.startswith(self._CACHED):
            with self._cache_lock:        # one reader at a time: a second thread gets the first one's answer
                hit = self._cache.get(path)
                if hit is not None and time.monotonic() - hit[0] < self.CACHE_SECONDS:
                    return hit[1]
                raw = self._request(path, None, headers)
                out = json.loads(raw) if raw else None
                self._cache[path] = (time.monotonic(), out)
                return out
        raw = self._request(path, data, headers)
        return json.loads(raw) if raw else None

    @staticmethod
    def _explain(code: int, body: str) -> str:
        """Readable message from a graph validation error (400 from /prompt)."""
        try:
            j = json.loads(body)
        except ValueError:
            return f"ComfyUI HTTP {code}: {body[:500]}"
        lines = []
        err = j.get("error")
        if isinstance(err, dict):
            lines.append(err.get("message", ""))
            if err.get("details"):
                lines.append(err["details"])
        for node_id, ne in (j.get("node_errors") or {}).items():
            for e in ne.get("errors", []):
                lines.append(f"node {node_id} ({ne.get('class_type')}): {e.get('message')} – {e.get('details')}")
        return "ComfyUI rejected the job:\n" + "\n".join(x for x in lines if x)

    # ---------- info ----------

    def system_stats(self) -> dict:
        return self._json("/system_stats")

    def object_info(self, node: str) -> dict:
        return self._json(f"/object_info/{urllib.parse.quote(node)}").get(node, {})

    def _choices(self, node: str, field: str) -> list[str]:
        try:
            spec = self.object_info(node)["input"]["required"][field]
        except (KeyError, ComfyError):
            return []
        # old format: [[...list...], {...}], new: ["COMBO", {"options": [...]}]
        if isinstance(spec[0], list):
            return spec[0]
        if len(spec) > 1 and isinstance(spec[1], dict):
            return spec[1].get("options", [])
        return []

    def checkpoints(self) -> list[str]:
        return self._choices("CheckpointLoaderSimple", "ckpt_name")

    def clips(self) -> list[str]:
        return self._choices("CLIPLoader", "clip_name")

    def loras(self) -> list[str]:
        return self._choices("LoraLoaderModelOnly", "lora_name")

    def samplers(self) -> list[str]:
        return self._choices("KSampler", "sampler_name")

    def schedulers(self) -> list[str]:
        return self._choices("KSampler", "scheduler")

    def _folder(self, folder: str) -> list[str]:
        """The files in one of ComfyUI's model folders (GET /models/<folder>); [] when it cannot be read."""
        try:
            j = self._json("/models/" + urllib.parse.quote(folder))
        except (ComfyError, ValueError):
            return []
        return [str(x) for x in j] if isinstance(j, list) else []

    def inventory_raw(self) -> dict:
        """Model files per loader kind (unet, clip, vae, lora) and, when readable, the names of all node classes
        ("nodes", one /object_info call; None when that failed). Raises ComfyError when the server cannot be reached,
        because the empty lists _choices gives then would look like "nothing is installed"."""
        self.system_stats()
        out = {
            "unet": self._choices("UNETLoader", "unet_name"),
            "clip": self._choices("CLIPLoader", "clip_name"),
            "vae": self._choices("VAELoader", "vae_name"),
            "lora": self._choices("LoraLoaderModelOnly", "lora_name"),
            "preview": self._folder("vae_approx"),      # the live preview decoders (TAESD) have no loader node
            "bg_removal": self._choices("LoadBackgroundRemovalModel", "bg_removal_name"),
        }
        try:
            out["nodes"] = set((self._json("/object_info") or {}).keys())
        except (ComfyError, ValueError):
            out["nodes"] = None
        return out

    # ---------- image I/O ----------

    def upload_image(self, image: Image.Image, name: str) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        boundary = uuid.uuid4().hex
        parts = []
        for key, value in (("overwrite", "true"), ("type", "input"), ("subfolder", "pccomfy")):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f"Content-Type: image/png\r\n\r\n".encode() + buf.getvalue() + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        raw = self._request("/upload/image", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        j = json.loads(raw)
        return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> Image.Image:
        q = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
        return Image.open(io.BytesIO(self._request(f"/view?{q}")))

    # ---------- execution ----------

    def queue(self, graph: dict, preview: str | None = None) -> str:
        """preview: ComfyUI's preview method for this prompt only ("taesd" uses the TAESD file of the model when it is in
        models/vae_approx and falls back to the coarse latent2rgb colours; "none"); None = ComfyUI's start setting."""
        if self.name_fixer is not None:
            self.name_fixer(graph)
        payload = {"prompt": graph, "client_id": self.client_id}
        if preview:
            payload["extra_data"] = {"preview_method": preview}
        j = self._json("/prompt", payload)
        if j.get("node_errors"):
            raise ComfyError(self._explain(400, json.dumps(j)))
        return j["prompt_id"]

    def interrupt(self, prompt_id: str | None = None) -> None:
        try:
            if prompt_id:
                self._json("/queue", {"delete": [prompt_id]})
            self._json("/interrupt", {"prompt_id": prompt_id} if prompt_id else {})
        except ComfyError:
            pass

    def history(self, prompt_id: str) -> dict | None:
        return self._json(f"/history/{prompt_id}").get(prompt_id)

    def wait(self, prompt_id: str, on_progress: Callable[..., None] | None = None,
             cancelled: Callable[[], bool] | None = None, timeout: float = 1800,
             on_preview: Callable[[Image.Image], None] | None = None) -> dict:
        """Wait for the job to finish. Progress via websocket when available, else poll /history. on_preview gets each
        live preview frame (a PIL image) the sampler sends."""
        # on_progress(fraction, message, node=<id of the node ComfyUI is executing, or None>);
        # fraction is -1 when the node reports no progress (e.g. a text model writing the prompt).
        on_progress = on_progress or (lambda f, msg, node=None: None)
        current = None
        cancelled = cancelled or (lambda: False)
        deadline = time.monotonic() + timeout
        ws = None
        if websocket is not None:
            try:
                ws_url = self.url.replace("http", "ws", 1) + f"/ws?clientId={self.client_id}"
                ws = websocket.create_connection(ws_url, timeout=1)
            except Exception:
                ws = None
        try:
            while time.monotonic() < deadline:
                if cancelled():
                    self.interrupt(prompt_id)
                    raise Cancelled()
                if ws is not None:
                    try:
                        msg = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        msg = None
                        on_progress(-1, "", current)  # heartbeat (~1/s): lets the UI show elapsed time
                    except Exception:
                        ws = None
                        msg = None
                    if isinstance(msg, (bytes, bytearray)):
                        im = preview_image(bytes(msg), prompt_id) if on_preview else None
                        if im is not None:
                            on_preview(im)
                        continue
                    if isinstance(msg, str):
                        m = json.loads(msg)
                        d = m.get("data", {})
                        if d.get("prompt_id") not in (None, prompt_id):
                            continue
                        if m["type"] == "executing" and d.get("node") is not None:
                            current = str(d["node"])
                            on_progress(-1, "", current)
                        elif m["type"] == "progress" and d.get("max"):
                            on_progress(d["value"] / d["max"], f"step {d['value']}/{d['max']}",
                                        str(d.get("node") or current or "") or None)
                        elif m["type"] == "execution_error":
                            raise ComfyError(f"Error in node {d.get('node_type')}: {d.get('exception_message')}")
                        elif m["type"] == "executing" and d.get("node") is None:
                            break
                        elif m["type"] == "execution_success":
                            break
                        continue
                else:
                    time.sleep(0.5)
                h = self.history(prompt_id)
                if h and h.get("status", {}).get("completed") is not None and (
                        h["status"].get("completed") or h["status"].get("status_str") == "error"):
                    break
                if ws is None:
                    on_progress(-1, "generating…", current)
            else:
                raise ComfyError("Timed out waiting for ComfyUI.")
        finally:
            if ws is not None:
                ws.close()
        h = self.history(prompt_id) or {}
        status = h.get("status", {})
        if status.get("status_str") == "error":
            msgs = [m[1].get("exception_message") for m in status.get("messages", []) if m[0] == "execution_error"]
            raise ComfyError("ComfyUI reported an error: " + ("; ".join(x for x in msgs if x) or "unknown"))
        return h

    def output_images(self, hist: dict, node_id: str | None = None) -> list[Image.Image]:
        outputs = hist.get("outputs", {})
        ids = [node_id] if node_id and node_id in outputs else list(outputs)
        images = []
        for nid in ids:
            for im in outputs[nid].get("images", []):
                images.append(self.view(im["filename"], im.get("subfolder", ""), im.get("type", "output")))
            if images:
                break
        if not images:
            raise ComfyError("The job finished without output images (no SaveImage/PreviewImage node?).")
        return images
