from __future__ import annotations

import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from server.api import Api

ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / "web"


class KeyguardianHandler(BaseHTTPRequestHandler):
    api = Api()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path.startswith("/api/"):
            self.api.handle_get(self, path)
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path.startswith("/api/"):
            self.api.handle_post(self, path)
            return

        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        # Keep request logging intentionally terse. Never log request bodies,
        # provider keys, model prompts, or synthetic secrets here.
        print(f"{self.address_string()} - {fmt % args}")

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()

        try:
            target.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self.send_error(403)
            return

        if not target.is_file():
            self.send_error(404)
            return

        content_type, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("Keyguardian must bind to 127.0.0.1 only")
    return ThreadingHTTPServer((host, port), KeyguardianHandler)
