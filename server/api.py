from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

from engine.floor_loader import FloorLoader
from engine.session_store import SessionStore


class Api:
    def __init__(self) -> None:
        self.floors = FloorLoader().load()
        self.sessions = SessionStore()

    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        if path == "/api/health":
            self._json(handler, 200, {"ok": True, "service": "keyguardian"})
            return

        if path == "/api/floors":
            self._json(
                handler,
                200,
                {
                    "floors": [floor.public_dict() for floor in self.floors],
                },
            )
            return

        self._json(handler, 404, {"error": "not_found"})

    def handle_post(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        # Message/provider/key endpoints intentionally come in the Floor 1 slice.
        # The scaffold keeps the API boundary in place without pretending those
        # security-sensitive flows are already implemented.
        self._discard_body(handler)
        self._json(handler, 501, {"error": "not_implemented"})

    @staticmethod
    def _discard_body(handler: BaseHTTPRequestHandler) -> None:
        length = int(handler.headers.get("Content-Length", "0") or "0")
        if length:
            handler.rfile.read(length)

    @staticmethod
    def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(data)
