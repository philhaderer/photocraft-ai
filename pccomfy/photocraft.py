"""Client for PhotoCraft's control channel (JSON lines over TCP).

PhotoCraft started with `--control <port>` listens on 127.0.0.1:<port>. The first frame must be
`auth` with the token, then every request is one JSON line:
    {"id": 1, "method": "engine.execute", "params": {"command": "...", "params": {...}}}
and every reply is one line {"id": 1, "ok": true, "result": ...}.

The same class also talks to `photocraft-cli serve --port` (headless, used by the tests):
only the file methods differ (app.open/app.save vs doc.open/doc.save).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path


class PhotoCraftError(RuntimeError):
    pass


class _Closed(PhotoCraftError):
    pass


class PhotoCraft:
    def __init__(self, host: str = "127.0.0.1", port: int = 7878, token: str | None = None,
                 token_file: str | Path | None = None, timeout: float = 90.0, headless: bool = False):
        self.host, self.port, self.timeout, self.headless = host, port, timeout, headless
        self.token = token
        self.token_file = Path(token_file).expanduser() if token_file else None
        self._sock: socket.socket | None = None
        self._buf = b""
        self._next_id = 0

    # ---------- transport ----------

    def connect(self) -> "PhotoCraft":
        if self._sock:
            return self
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=5)
        except OSError as e:
            raise PhotoCraftError(
                f"Can't connect to PhotoCraft at {self.host}:{self.port} ({e}). "
                "Is PhotoCraft running with --control?") from e
        self._sock.settimeout(self.timeout)
        token = self.token
        if token is None and self.token_file and self.token_file.exists():
            token = self.token_file.read_text().strip()  # read on every connect: PhotoCraft may have renewed it
        if not token:
            self.close()
            raise PhotoCraftError(f"No control-channel token (file {self.token_file}).")
        reply = self._roundtrip("auth", {"token": token}, req_id="auth")
        if not reply.get("ok"):
            self.close()
            raise PhotoCraftError(f"PhotoCraft rejected the token: {reply.get('error')}")
        return self

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None
                self._buf = b""

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    def _readline(self) -> bytes:
        while b"\n" not in self._buf:
            chunk = self._sock.recv(1 << 16)
            if not chunk:
                raise _Closed("PhotoCraft closed the connection.")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line

    def _roundtrip(self, method: str, params: dict | None, req_id=None) -> dict:
        if req_id is None:
            self._next_id += 1
            req_id = self._next_id
        frame = json.dumps({"id": req_id, "method": method, "params": params or {}}) + "\n"
        try:
            self._sock.sendall(frame.encode())
            while True:
                reply = json.loads(self._readline())
                if reply.get("id") == req_id:
                    return reply
        except socket.timeout as e:
            self.close()
            raise PhotoCraftError(f"No reply from PhotoCraft to `{method}`.") from e

    def call(self, method: str, params: dict | None = None):
        self.connect()
        try:
            reply = self._roundtrip(method, params)
        except (OSError, ConnectionError, _Closed):
            # PhotoCraft may have been restarted – reconnect once
            self.close()
            self.connect()
            reply = self._roundtrip(method, params)
        if not reply.get("ok"):
            raise PhotoCraftError(f"{method}: {reply.get('error')}")
        return reply.get("result")

    def execute(self, command: str, params: dict | None = None):
        try:
            return self.call("engine.execute", {"command": command, "params": params or {}})
        except PhotoCraftError as e:
            raise PhotoCraftError(f"{command}: {e}") from None

    # ---------- shared operations (desktop and headless) ----------

    def session(self) -> dict:
        """{"active": index, "documents": [{index, name, width, height, ...}]}"""
        if self.headless:
            return self.call("session.list")
        try:
            return self.call("ui.inspect")["session"]
        except (PhotoCraftError, KeyError, TypeError):
            # newer PhotoCraft builds: the same data as an engine command
            res = self.execute("session.inspect")
            return res.get("session", res) if isinstance(res, dict) else res

    def document(self) -> dict:
        return self.execute("document.inspect")

    def save(self, path: str) -> dict:
        """Save the active document under the automation write root (format from the extension)."""
        return self.call("doc.save" if self.headless else "app.save", {"path": path})

    def open(self, path: str) -> dict:
        """Open a file from the automation read root as a new (active) document."""
        return self.call("doc.open" if self.headless else "app.open", {"path": path})

    def close_active(self) -> None:
        """Close the active document without saving."""
        self.execute("file.close")
        if not self.headless:
            # If the app asks about unsaved changes after all, answer "Don't Save".
            try:
                dialogs = self.call("ui.inspect").get("dialogs", [])
                if any(d.get("id") == "discard" for d in dialogs):
                    self.call("ui.dialog.confirm", {"dialog": "discard", "choice": "dontSave"})
            except PhotoCraftError:
                pass

    def activate(self, index: int) -> None:
        self.execute("document.activate", {"document": index})

    def ping(self) -> dict:
        s = self.session()
        return {"documents": len(s.get("documents", [])), "active": s.get("active")}
