"""HTTP routes, session cookies and per-game serialization."""

from __future__ import annotations

import json
import logging
from functools import partial
from http.cookies import CookieError, SimpleCookie
from typing import TYPE_CHECKING, Any

from engine.errors import RequestError
from engine.game import Game
from engine.limits import GameLimits
from engine.models import ModelService
from engine.providers.base import Provider, ProviderError
from engine.secret_store import SecretStore
from engine.session_store import Session, SessionStore
from engine.settings import Settings

if TYPE_CHECKING:
    from server.wsgi import Response

MAX_BODY_BYTES = 64 * 1024
SESSION_COOKIE = "kg_session"
logger = logging.getLogger("keyguardian")


class Api:
    def __init__(self, settings: Settings | None = None, provider: Provider | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.secrets = SecretStore()
        self.limits = GameLimits(self.settings)
        self.models = ModelService(self.settings, self.secrets, self.limits, provider)
        self.game = Game(self.models)
        self.sessions = SessionStore(
            max_sessions=self.settings.max_sessions,
            max_per_owner=self.settings.max_sessions_per_owner,
            max_per_network=self.settings.max_sessions_per_ip,
            idle_seconds=self.settings.session_idle_seconds,
            max_seconds=self.settings.session_max_seconds,
            on_expire=self.secrets.clear_session,
        )
        # All session routes share one lock/error/cookie boundary.
        self.routes = {
            ("GET", "/api/state"): lambda session, body, network: self.game.state(session),
            ("POST", "/api/models"): lambda session, body, network: self.models.list_models(body),
            ("POST", "/api/keys"): lambda session, body, network: self.game.configure(
                session, body
            ),
            ("POST", "/api/keys/clear"): lambda session, body, network: self.models.clear(session),
            ("POST", "/api/message"): partial(self._chat, action="send"),
            ("POST", "/api/message/edit"): partial(self._chat, action="edit"),
            ("POST", "/api/message/regenerate"): partial(self._chat, action="regenerate"),
            ("POST", "/api/code"): lambda session, body, network: self.game.submit_code(
                session, body
            ),
            ("POST", "/api/floor/select"): lambda session, body, network: self.game.select_floor(
                session, body
            ),
            ("POST", "/api/floor/next"): lambda session, body, network: self.game.advance(session),
            ("POST", "/api/floor/skip"): lambda session, body, network: self.game.advance(
                session, skip=True
            ),
            ("POST", "/api/reset/conversation"): lambda session, body, network: self.game.reset(
                session
            ),
            ("POST", "/api/reset/floor"): lambda session, body, network: self.game.reset(
                session, floor=True
            ),
        }

    def _chat(self, session, body, network, *, action):
        return self.game.chat(session, body, action=action, network_id=network)

    def dispatch(self, handler: Response, path: str, method: str) -> None:
        session = None
        acquired = False
        handler.session_result = None
        try:
            if method == "GET" and path == "/api/health":
                self._json(handler, 200, {"ok": True, "service": "keyguardian"})
                return
            if method == "GET" and path == "/api/floors":
                self._json(
                    handler, 200, {"floors": [floor.public_dict() for floor in self.game.floors]}
                )
                return
            operation = self.routes.get((method, path))
            if operation is None:
                raise RequestError(404, "not_found")
            network = getattr(handler, "network_id", "")
            shared = self.settings.deployment == "shared"
            if shared:
                self.limits.request(network, limit=self.settings.ip_requests_per_minute)
            session, is_new = self._session_for(handler)
            handler.session_result = (session, is_new)
            if shared:
                self.limits.request("session:" + session.session_id)
            acquired = session.lock.acquire(blocking=False)
            if not acquired:
                raise RequestError(
                    409,
                    "game_busy",
                    "Your guardian is still responding. Please wait and try again.",
                )
            if method == "POST" and path in {"/api/keys", "/api/keys/clear", "/api/models"}:
                self.models.require_local()
            body = self._read_json(handler) if method == "POST" else {}
            self._json(handler, 200, operation(session, body, network))
        except RequestError as exc:
            self._json(handler, exc.status, exc.public_dict())
        except ProviderError as exc:
            logger.warning("event=inference outcome=provider_error")
            self._json(handler, 502, {"error": "provider_error", "message": exc.message})
        finally:
            if acquired:
                session.lock.release()

    def _session_for(self, handler: Response) -> tuple[Session, bool]:
        owner_id = getattr(handler, "owner_id", "")
        cookie = SimpleCookie()
        try:
            cookie.load(handler.headers.get("Cookie", ""))
        except CookieError:
            raise RequestError(400, "invalid_cookie", "Please reload the page.") from None
        morsel = cookie.get(SESSION_COOKIE)
        if morsel is not None:
            session = self.sessions.get(morsel.value, owner_id)
            if session is not None:
                return session, False
        session = self.sessions.create(owner_id, network_id=getattr(handler, "network_id", ""))
        self.game.initialize(session)
        return session, True

    @staticmethod
    def _read_json(handler: Response) -> dict[str, Any]:
        content_type = handler.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip().lower() != "application/json":
            raise RequestError(400, "bad_request", "Content-Type must be application/json")

        try:
            length = int(handler.headers.get("Content-Length", "0") or "0")
        except ValueError:
            raise RequestError(400, "bad_request", "Invalid Content-Length") from None
        if length <= 0 or length > MAX_BODY_BYTES:
            raise RequestError(400, "bad_request", "Request body is empty or too large")

        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise RequestError(400, "bad_request", "Incomplete request body")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RequestError(
                400, "bad_request", "Request body must contain valid UTF-8 JSON"
            ) from None
        if not isinstance(payload, dict):
            raise RequestError(400, "bad_request", "JSON body must be an object")
        return payload

    def _json(
        self,
        handler: Response,
        status: int,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> None:
        if session_id is None:
            session_result = getattr(handler, "session_result", None)
            if session_result is not None and session_result[1]:
                session_id = session_result[0].session_id
        data = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "no-referrer")
        if session_id is not None:
            handler.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={session_id}; Path=/; HttpOnly; SameSite=Strict"
                + ("; Secure" if self.settings.secure_cookies else ""),
            )
        handler.end_headers()
        handler.wfile.write(data)
