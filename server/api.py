from __future__ import annotations

import hmac
import json
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from typing import Any

from engine.floor_loader import FloorLoader
from engine.prompt_loader import PromptLoader
from engine.providers.base import ChatMessage, ProviderError
from engine.providers.registry import SUPPORTED_PROVIDERS, create_provider, default_model
from engine.secret_store import SecretStore
from engine.session_store import Session, SessionStore

MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 12_000
MAX_CODE_CHARS = 128
SESSION_COOKIE = "kg_session"


class Api:
    def __init__(self) -> None:
        self.floors = FloorLoader().load()
        self.prompts = PromptLoader()
        self.sessions = SessionStore()
        self.secrets = SecretStore()

    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        if path == "/api/health":
            self._json(handler, 200, {"ok": True, "service": "keyguardian"})
            return

        if path == "/api/floors":
            self._json(
                handler,
                200,
                {"floors": [floor.public_dict() for floor in self.floors]},
            )
            return

        if path == "/api/state":
            session, is_new = self._session_for(handler)
            with session.lock:
                floor = self.floors[session.floor_number - 1]
                payload = {
                    "session": {
                        "floor": floor.public_dict(),
                        "cleared": session.floor_number in session.cleared_floors,
                        "key_configured": self.secrets.has_provider_key(
                            session.session_id, session.provider
                        ),
                        "provider": session.provider,
                        "model": session.model,
                        "conversation": self._conversation_payload(session),
                    },
                    "providers": {
                        provider: {"default_model": default_model(provider)}
                        for provider in SUPPORTED_PROVIDERS
                    },
                }
            self._json(
                handler,
                200,
                payload,
                session_id=session.session_id if is_new else None,
            )
            return

        self._json(handler, 404, {"error": "not_found"})

    def handle_post(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        session, is_new = self._session_for(handler)
        try:
            payload = self._read_json(handler)
        except ValueError as exc:
            self._json(
                handler,
                400,
                {"error": "bad_request", "message": str(exc)},
                session_id=session.session_id if is_new else None,
            )
            return

        if path == "/api/models":
            self._list_models(handler, session, payload, is_new)
            return

        if path == "/api/keys":
            self._configure_key(handler, session, payload, is_new)
            return

        if path == "/api/keys/clear":
            self.secrets.clear_session(session.session_id)
            self._json(
                handler,
                200,
                {"ok": True, "key_configured": False},
                session_id=session.session_id if is_new else None,
            )
            return

        if path == "/api/message":
            self._message(handler, session, payload, is_new)
            return

        if path == "/api/message/edit":
            self._edit_last_message(handler, session, payload, is_new)
            return

        if path == "/api/message/regenerate":
            self._regenerate_last_response(handler, session, is_new)
            return

        if path == "/api/code":
            self._submit_code(handler, session, payload, is_new)
            return

        if path == "/api/reset/conversation":
            opening = self.prompts.load(session.floor_number).opening_message
            session.reset_conversation(opening)
            self._json(
                handler,
                200,
                {
                    "ok": True,
                    "conversation": self._conversation_payload(session),
                },
                session_id=session.session_id if is_new else None,
            )
            return

        if path == "/api/reset/floor":
            opening = self.prompts.load(session.floor_number).opening_message
            session.reset_floor(opening)
            self._json(
                handler,
                200,
                {
                    "ok": True,
                    "conversation": self._conversation_payload(session),
                    "cleared": False,
                },
                session_id=session.session_id if is_new else None,
            )
            return

        self._json(
            handler,
            404,
            {"error": "not_found"},
            session_id=session.session_id if is_new else None,
        )

    def _list_models(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        payload: dict[str, Any],
        is_new: bool,
    ) -> None:
        provider_name = payload.get("provider", "gemini")
        api_key = payload.get("api_key")

        if provider_name not in SUPPORTED_PROVIDERS:
            self._json(handler, 400, {"error": "unsupported_provider"})
            return
        if not isinstance(api_key, str) or not api_key.strip():
            self._json(handler, 400, {"error": "missing_api_key"})
            return
        if len(api_key) > 2048:
            self._json(handler, 400, {"error": "invalid_api_key"})
            return

        try:
            provider = create_provider(provider_name, api_key.strip())
            models = provider.list_models()
        except ProviderError as exc:
            self._json(
                handler,
                502,
                {"error": "provider_error", "message": exc.message},
                session_id=session.session_id if is_new else None,
            )
            return

        self._json(
            handler,
            200,
            {
                "provider": provider_name,
                "default_model": default_model(provider_name),
                "models": [model.public_dict() for model in models],
            },
            session_id=session.session_id if is_new else None,
        )

    def _configure_key(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        payload: dict[str, Any],
        is_new: bool,
    ) -> None:
        provider = payload.get("provider", "gemini")
        api_key = payload.get("api_key")
        model = payload.get("model")

        if provider not in SUPPORTED_PROVIDERS:
            self._json(handler, 400, {"error": "unsupported_provider"})
            return
        if not isinstance(api_key, str) or not api_key.strip():
            self._json(handler, 400, {"error": "missing_api_key"})
            return
        if len(api_key) > 2048:
            self._json(handler, 400, {"error": "invalid_api_key"})
            return

        if model is None or (isinstance(model, str) and not model.strip()):
            normalized_model = default_model(provider)
        elif isinstance(model, str):
            normalized_model = model.strip()
            if not (1 <= len(normalized_model) <= 100):
                self._json(handler, 400, {"error": "invalid_model"})
                return
        else:
            self._json(handler, 400, {"error": "invalid_model"})
            return

        with session.lock:
            provider_changed = session.provider != provider
            session.provider = provider
            session.model = normalized_model
            if provider_changed:
                opening = self.prompts.load(session.floor_number).opening_message
                session.reset_conversation(opening)

        self.secrets.set_provider_key(session.session_id, provider, api_key.strip())
        self._json(
            handler,
            200,
            {
                "ok": True,
                "provider": provider,
                "model": normalized_model,
                "key_configured": True,
            },
            session_id=session.session_id if is_new else None,
        )

    def _message(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        payload: dict[str, Any],
        is_new: bool,
    ) -> None:
        message = self._validated_message(handler, payload)
        if message is None:
            return

        with session.lock:
            api_key = self._chat_api_key(handler, session)
            if api_key is None:
                return

            user_message = ChatMessage(role="user", content=message)
            candidate_conversation = [*session.conversation, user_message]
            assistant_text = self._complete_chat(
                handler,
                session,
                api_key,
                candidate_conversation,
                is_new,
            )
            if assistant_text is None:
                return

            session.conversation.extend(
                [user_message, ChatMessage(role="assistant", content=assistant_text)]
            )
            turns = self._turn_count(session)
            conversation = self._conversation_payload(session)

        self._json(
            handler,
            200,
            {"reply": assistant_text, "turns": turns, "conversation": conversation},
            session_id=session.session_id if is_new else None,
        )

    def _edit_last_message(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        payload: dict[str, Any],
        is_new: bool,
    ) -> None:
        message = self._validated_message(handler, payload)
        if message is None:
            return

        with session.lock:
            if not session.has_revisable_exchange():
                self._json(
                    handler,
                    409,
                    {
                        "error": "no_message_to_edit",
                        "message": "There is no completed player message to edit yet.",
                    },
                    session_id=session.session_id if is_new else None,
                )
                return

            api_key = self._chat_api_key(handler, session)
            if api_key is None:
                return

            edited_user = ChatMessage(role="user", content=message)
            candidate_conversation = [*session.conversation[:-2], edited_user]
            assistant_text = self._complete_chat(
                handler,
                session,
                api_key,
                candidate_conversation,
                is_new,
            )
            if assistant_text is None:
                return

            session.replace_last_exchange(message, assistant_text)
            turns = self._turn_count(session)
            conversation = self._conversation_payload(session)

        self._json(
            handler,
            200,
            {"reply": assistant_text, "turns": turns, "conversation": conversation},
            session_id=session.session_id if is_new else None,
        )

    def _regenerate_last_response(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        is_new: bool,
    ) -> None:
        with session.lock:
            if not session.has_revisable_exchange():
                self._json(
                    handler,
                    409,
                    {
                        "error": "no_response_to_regenerate",
                        "message": "There is no completed guardian response to regenerate yet.",
                    },
                    session_id=session.session_id if is_new else None,
                )
                return

            api_key = self._chat_api_key(handler, session)
            if api_key is None:
                return

            candidate_conversation = list(session.conversation[:-1])
            assistant_text = self._complete_chat(
                handler,
                session,
                api_key,
                candidate_conversation,
                is_new,
            )
            if assistant_text is None:
                return

            session.replace_last_reply(assistant_text)
            turns = self._turn_count(session)
            conversation = self._conversation_payload(session)

        self._json(
            handler,
            200,
            {"reply": assistant_text, "turns": turns, "conversation": conversation},
            session_id=session.session_id if is_new else None,
        )

    def _validated_message(
        self,
        handler: BaseHTTPRequestHandler,
        payload: dict[str, Any],
    ) -> str | None:
        message = payload.get("message")
        if not isinstance(message, str):
            self._json(handler, 400, {"error": "invalid_message"})
            return None
        message = message.strip()
        if not message or len(message) > MAX_MESSAGE_CHARS:
            self._json(handler, 400, {"error": "invalid_message"})
            return None
        return message

    def _chat_api_key(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
    ) -> str | None:
        floor = self.floors[session.floor_number - 1]
        if not floor.implemented:
            self._json(handler, 409, {"error": "floor_not_implemented"})
            return None

        api_key = self.secrets.get_provider_key(session.session_id, session.provider)
        if api_key is None:
            self._json(handler, 409, {"error": "api_key_required"})
            return None
        return api_key

    def _complete_chat(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        api_key: str,
        conversation: list[ChatMessage],
        is_new: bool,
    ) -> str | None:
        prompt = self.prompts.load(session.floor_number)
        system_prompt = prompt.render_system(vault_code=session.vault_code)
        messages = [ChatMessage(role="system", content=system_prompt), *conversation]

        try:
            provider = create_provider(session.provider, api_key)
            return provider.complete(messages=messages, model=session.model)
        except ProviderError as exc:
            self._json(
                handler,
                502,
                {"error": "provider_error", "message": exc.message},
                session_id=session.session_id if is_new else None,
            )
            return None

    def _submit_code(
        self,
        handler: BaseHTTPRequestHandler,
        session: Session,
        payload: dict[str, Any],
        is_new: bool,
    ) -> None:
        candidate = payload.get("code")
        if not isinstance(candidate, str) or len(candidate) > MAX_CODE_CHARS:
            self._json(handler, 400, {"error": "invalid_code"})
            return

        normalized_candidate = candidate.strip().upper()
        with session.lock:
            correct = hmac.compare_digest(normalized_candidate, session.vault_code)
            if correct:
                session.cleared_floors.add(session.floor_number)
            cleared = session.floor_number in session.cleared_floors

        self._json(
            handler,
            200,
            {
                "correct": correct,
                "cleared": cleared,
                "next_floor_available": False,
            },
            session_id=session.session_id if is_new else None,
        )

    def _session_for(self, handler: BaseHTTPRequestHandler) -> tuple[Session, bool]:
        cookie = SimpleCookie()
        cookie.load(handler.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        if morsel is not None:
            session = self.sessions.get(morsel.value)
            if session is not None:
                return session, False

        session = self.sessions.create()
        opening = self.prompts.load(session.floor_number).opening_message
        session.reset_conversation(opening)
        return session, True

    @staticmethod
    def _turn_count(session: Session) -> int:
        return sum(1 for item in session.conversation if item.role == "user")

    @staticmethod
    def _conversation_payload(session: Session) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content}
            for message in session.conversation
        ]

    @staticmethod
    def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        content_type = handler.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            raise ValueError("Content-Type must be application/json")

        try:
            length = int(handler.headers.get("Content-Length", "0") or "0")
        except ValueError:
            raise ValueError("Invalid Content-Length") from None
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body is empty or too large")

        raw = handler.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Request body must contain valid UTF-8 JSON") from None
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    @staticmethod
    def _json(
        handler: BaseHTTPRequestHandler,
        status: int,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> None:
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
                f"{SESSION_COOKIE}={session_id}; Path=/; HttpOnly; SameSite=Strict",
            )
        handler.end_headers()
        handler.wfile.write(data)
