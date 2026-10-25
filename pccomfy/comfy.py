"""Minimal ComfyUI API client (standard library + Pillow only).

Endpoints used:
  GET  /system_stats, /object_info/<Node>   – connection check, model/sampler lists
  POST /upload/image                         – upload image and mask (land in input/)
  POST /prompt                               – queue an API-format graph
  WS   /ws?clientId=…                        – progress (optional, needs websocket-client)
  GET  /history/<prompt_id>, /view           – fetch results
  POST /interrupt, /queue                    – cancel
"""

from __future__ import annotations

import io
import json
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
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


class ComfyUI:
    def __init__(self, url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    # ---------- HTTP ----------

    def _request(self, path: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None):
        req = urllib.request.Request(self.url + path, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise ComfyError(self._explain(e.code, body)) from None
        except urllib.error.URLError as e:
            raise ComfyError(f"No connection to ComfyUI at {self.url} ({e.reason}). Is the server running?") from None

    def _json(self, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"} if data else {}
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

    def fooocus_inpaint(self) -> tuple[str, str] | None:
        """(head, patch) if the server has comfyui-inpaint-nodes and the Fooocus files in models/inpaint."""
        files = self._choices("INPAINT_LoadFooocusInpaint", "head")
        heads = [f for f in files if "head" in f.lower()]
        patches = sorted((f for f in files if f.lower().endswith(".patch") or "inpaint_v2" in f.lower()), reverse=True)
        if heads and patches:
            return heads[0], patches[0]  # sorted descending: newest patch (v26 > v25) first
        return None

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

    def queue(self, graph: dict) -> str:
        j = self._json("/prompt", {"prompt": graph, "client_id": self.client_id})
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
             cancelled: Callable[[], bool] | None = None, timeout: float = 1800) -> dict:
        """Wait for the job to finish. Progress via websocket when available, else poll /history."""
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
