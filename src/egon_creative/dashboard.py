"""Read-only loopback dashboard; no approval or publication side effects over HTTP."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlparse


def serve(store, port=8765):
    template = (Path(__file__).parent / "web/index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                return self.respond(200, "text/html; charset=utf-8", template)
            if path == "/api/state":
                snapshot = store.snapshot()
                # Do not expose local source paths, raw integration data or credentials.
                for asset in snapshot["assets"]:
                    asset.pop("path", None)
                for job in snapshot["jobs"]:
                    job.pop("output_path", None)
                    job["title"] = store.storyboard(job["id"])["title"]
                return self.respond(200, "application/json", json.dumps(snapshot, ensure_ascii=False).encode())
            match = re.fullmatch(r"/video/(EGON-VIDEO-[0-9a-f]{16})", path)
            if match:
                try:
                    job = store.job(match[1])
                except KeyError:
                    return self.respond(404, "text/plain", b"Unknown job")
                if job["output_path"]:
                    target = Path(job["output_path"]).resolve()
                    state_root = store.path.parent.resolve()
                    if target.is_relative_to(state_root) and target.is_file():
                        # Local preview sizes are bounded by the production runtime.
                        return self.respond(200, "video/mp4", target.read_bytes())
            self.respond(404, "text/plain", b"Not found")

        def respond(self, code, mime, data):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; media-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    print(f"EGON dashboard: http://127.0.0.1:{port} — read only", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
