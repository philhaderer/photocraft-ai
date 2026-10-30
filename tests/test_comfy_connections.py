"""ComfyUI client connections: GETs share one keep-alive connection, the lists are read at most once per 10 s (also when two
threads ask at once), a POST has a connection of its own, errors become ComfyError. A real local HTTP server counts them.

    python tests/test_comfy_connections.py
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import comfy  # noqa: E402

STATS = {"requests": [], "connections": 0, "close_next": False}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        STATS["connections"] += 1

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if STATS["close_next"]:
            STATS["close_next"] = False
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        STATS["requests"].append(self.path)
        if self.path.startswith("/object_info/"):
            node = self.path.rsplit("/", 1)[1]
            return self._send(200, {node: {"input": {"required": {"x": [["a", "b"], {}]}}}})
        self._send(200, {"ok": True})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        STATS["requests"].append("POST " + self.path)
        if self.path == "/bad":
            return self._send(400, {"error": {"message": "nope"}})
        self._send(200, {"prompt_id": "p1"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    c = comfy.ComfyUI(f"http://127.0.0.1:{srv.server_port}")

    for node in ("A", "B", "C", "D", "E", "F"):          # six lists on one connection
        c.object_info(node)
    assert STATS["connections"] == 1 and len(STATS["requests"]) == 6, STATS

    n = len(STATS["requests"])
    c.object_info("A"); c.system_stats(); c.system_stats()   # cached: the same node, and the stats once
    assert len(STATS["requests"]) == n + 1, STATS["requests"]

    # two threads (refresh and detection) ask for the same list at once: one request
    c.invalidate()
    n = len(STATS["requests"])
    ts = [threading.Thread(target=lambda: c.object_info("Z")) for _ in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(STATS["requests"]) == n + 1, STATS["requests"][n:]

    # the cache runs out
    old = comfy.ComfyUI.CACHE_SECONDS
    comfy.ComfyUI.CACHE_SECONDS = 0.0
    try:
        n = len(STATS["requests"])
        c.object_info("Z"); c.object_info("Z")
        assert len(STATS["requests"]) == n + 2
    finally:
        comfy.ComfyUI.CACHE_SECONDS = old

    # the server closes the idle connection: a GET goes on a new one
    c.invalidate()
    STATS["close_next"] = True
    c.object_info("Q")
    assert c.object_info("R")["input"]                      # (this one meets the closed connection)
    assert c.history  # (attribute exists)

    # a POST: its own connection, the answer comes back; an HTTP error becomes a ComfyError
    before = STATS["connections"]
    assert c._json("/prompt", {"prompt": {}})["prompt_id"] == "p1"
    assert STATS["connections"] == before + 1
    try:
        c._json("/bad", {})
        raise AssertionError("HTTP 400 must raise")
    except comfy.ComfyError as e:
        assert "nope" in str(e)

    srv.shutdown()
    srv.server_close()
    try:
        comfy.ComfyUI(f"http://127.0.0.1:{srv.server_port}", timeout=2).system_stats()
        raise AssertionError("a dead server must raise")
    except comfy.ComfyError as e:
        assert "No connection" in str(e)
    print("ok")


if __name__ == "__main__":
    main()
