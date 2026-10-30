"""downloads.py against a local HTTP server: .part file, resume (Range), size and SHA-256, cancel, free space, token hosts.

    python tests/test_downloads.py
"""
import hashlib
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import downloads, manifest  # noqa: E402

DATA = bytes(range(256)) * 4096 * 3          # 3 MB
SHA = hashlib.sha256(DATA).hexdigest()
SEEN = []                                    # (path, Range header, Authorization header, Host)
MODE = {"ignore_range": False, "cut_after": 0, "status": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        auth, rng = self.headers.get("Authorization"), self.headers.get("Range")
        SEEN.append((self.path, rng, auth, self.headers.get("Host")))
        if self.path == "/hop":                      # a redirect to another host name (127.0.0.1 -> localhost)
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{self.server.server_port}/file")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if MODE["status"]:
            self.send_response(MODE["status"])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start = 0
        if rng and not MODE["ignore_range"]:
            start = int(rng.split("=")[1].rstrip("-"))
            if start >= len(DATA):
                self.send_response(416)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(206)
        else:
            self.send_response(200)
        body = DATA[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if MODE["cut_after"]:                        # the connection breaks off after that many bytes
            self.wfile.write(body[:MODE["cut_after"]])
            self.wfile.flush()
            self.connection.close()
            return
        self.wfile.write(body)


def expect_error(fn, word, exc=downloads.DownloadError):
    try:
        fn()
    except exc as e:
        assert word in str(e), str(e)
        return
    raise AssertionError("expected an error with: " + word)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/file"
    tmp = Path(tempfile.mkdtemp())
    n = len(DATA)

    # a clean download: progress, hash checked, .part gone
    steps = []
    dest = tmp / "a" / "x.safetensors"
    out = downloads.download(url, dest, size=n, sha256=SHA, progress=lambda d, t, ph: steps.append((d, t, ph)))
    assert out == dest and dest.read_bytes() == DATA and not (tmp / "a" / "x.safetensors.part").exists()
    assert steps[0][2] == "downloading" and steps[-1][2] == "verifying" and steps[-1][0] == steps[-1][1] == n
    assert downloads.download(url, dest) == dest and len(SEEN) == 1          # already there: nothing is fetched

    # interrupted: the .part stays, the next call goes on with a Range request and the result is whole
    dest = tmp / "b.safetensors"
    MODE["cut_after"] = 1_000_000
    expect_error(lambda: downloads.download(url, dest, size=n, sha256=SHA), "go on")
    part = tmp / "b.safetensors.part"
    assert part.exists() and part.stat().st_size == 1_000_000 and not dest.exists()
    MODE["cut_after"] = 0
    downloads.download(url, dest, size=n, sha256=SHA)
    assert SEEN[-1][1] == "bytes=1000000-" and dest.read_bytes() == DATA and not part.exists()

    # a server that ignores Range sends the whole file again: the part is not appended twice
    dest = tmp / "c.safetensors"
    (tmp / "c.safetensors.part").write_bytes(DATA[:500])
    MODE["ignore_range"] = True
    downloads.download(url, dest, size=n, sha256=SHA)
    MODE["ignore_range"] = False
    assert dest.read_bytes() == DATA

    # a part file that is already complete (416) is verified and renamed
    dest = tmp / "d.safetensors"
    (tmp / "d.safetensors.part").write_bytes(DATA)
    downloads.download(url, dest, size=n, sha256=SHA)
    assert dest.read_bytes() == DATA

    # wrong checksum: deleted, nothing renamed; wrong size: reported
    dest = tmp / "e.safetensors"
    expect_error(lambda: downloads.download(url, dest, size=n, sha256="0" * 64), "checksum")
    assert not dest.exists() and not (tmp / "e.safetensors.part").exists()
    expect_error(lambda: downloads.download(url, dest, size=n + 10), "Incomplete")
    (tmp / "e.safetensors.part").unlink()

    # cancel keeps the part for a resume
    dest = tmp / "f.safetensors"
    ticks = []
    expect_error(lambda: downloads.download(url, dest, size=n, progress=lambda *a: ticks.append(1), cancel=lambda: len(ticks) >= 1),
                 "Cancelled", downloads.Cancelled)
    assert (tmp / "f.safetensors.part").exists() and not dest.exists()
    downloads.download(url, dest, size=n, sha256=SHA)
    assert dest.read_bytes() == DATA

    # server answers: login/licence and not found are said in words
    for code, word in ((403, "licence"), (404, "404")):
        MODE["status"] = code
        expect_error(lambda: downloads.download(url, tmp / f"g{code}.safetensors"), word)
    MODE["status"] = 0
    assert not (tmp / "g403.safetensors").exists()

    # free space: refused before anything is fetched
    before = len(SEEN)
    orig = downloads.free_space
    downloads.free_space = lambda p: 10_000_000
    try:
        expect_error(lambda: downloads.download(url, tmp / "h.safetensors", size=5_000_000_000), "free space")
    finally:
        downloads.free_space = orig
    assert len(SEEN) == before and downloads.free_space(tmp / "does" / "not" / "exist") > 0

    # the token goes only to its hosts, and is dropped when a redirect leaves them
    SEEN.clear()
    downloads.download(url, tmp / "i.safetensors", token="TOKEN", token_hosts=("example.org",))
    assert SEEN[0][2] is None                                             # not the token's host: not sent
    SEEN.clear()
    hop = f"http://127.0.0.1:{srv.server_port}/hop"
    downloads.download(hop, tmp / "j.safetensors", token="TOKEN", token_hosts=("127.0.0.1",))
    assert SEEN[0][2] == "Bearer TOKEN" and SEEN[1][0] == "/file" and SEEN[1][2] is None, SEEN     # dropped at the other host

    # the target: <models>/<folder>/<name>, a LoRA keeps its sub-folder, nothing leaves the models folder
    f = manifest.FILES["flux2-vae.safetensors"]
    assert downloads.target_for(tmp, f) == (tmp / "vae" / "flux2-vae.safetensors").resolve()
    lora = next(x for x in manifest.FILES.values() if x.kind == "lora" and "\\" in x.name)
    assert downloads.target_for(tmp, lora).parent.name == lora.name.split("\\")[0]
    expect_error(lambda: downloads.target_for(tmp, manifest.File("..\\..\\evil.safetensors", "lora")), "outside")
    srv.shutdown()
    print("ok")


if __name__ == "__main__":
    main()
