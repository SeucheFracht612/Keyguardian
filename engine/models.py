"""Provider selection, local credentials and bounded model calls."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Any

from engine.errors import RequestError
from engine.limits import GameLimits
from engine.providers.base import ChatMessage, Provider, ProviderError
from engine.providers.registry import PROVIDERS, catalog, create_provider, default_model
from engine.secret_store import SecretStore
from engine.session_store import Session
from engine.settings import Settings

logger = logging.getLogger("keyguardian")


def managed_provider(settings: Settings) -> Provider | None:
    if settings.llm_backend == "gemini":
        from engine.providers.gemini import GeminiProvider

        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key or len(key) > 2048 or any(char.isspace() for char in key):
            raise ValueError(
                "Set GEMINI_API_KEY securely on the server before starting Gemini mode"
            )
        return GeminiProvider(key, max_output_tokens=settings.max_output_tokens, managed=True)
    return None


class ModelService:
    def __init__(
        self,
        settings: Settings,
        secrets: SecretStore,
        limits: GameLimits,
        provider: Provider | None = None,
    ) -> None:
        self.settings = settings
        self.secrets = secrets
        self.limits = limits
        self.provider = provider if provider is not None else managed_provider(settings)

    @property
    def managed(self) -> bool:
        return self.provider is not None

    def initialize(self, session: Session) -> None:
        if self.managed:
            session.provider = self.settings.llm_backend
            session.model = self.settings.gemini_model

    def configured(self, session: Session) -> bool:
        return self.managed or self.secrets.has_provider_key(session.session_id, session.provider)

    def catalog(self) -> dict[str, dict[str, str]]:
        if self.managed:
            return {}
        return catalog()

    def require_local(self) -> None:
        if self.managed:
            raise RequestError(403, "server_managed_model")

    def _credentials(self, payload: dict[str, Any]) -> tuple[str, str]:
        self.require_local()
        name = payload.get("provider", "gemini")
        if not isinstance(name, str) or name not in PROVIDERS:
            raise RequestError(400, "unsupported_provider")
        key = payload.get("api_key")
        if not isinstance(key, str) or not key.strip():
            raise RequestError(400, "missing_api_key")
        if len(key) > 2048:
            raise RequestError(400, "invalid_api_key")
        return name, key.strip()

    def list_models(self, payload: dict[str, Any]) -> dict[str, Any]:
        name, key = self._credentials(payload)
        models = create_provider(name, key).list_models()
        return {
            "provider": name,
            "default_model": default_model(name),
            "models": [model.public_dict() for model in models],
        }

    def configure(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        name, key = self._credentials(payload)
        model = payload.get("model")
        if model is None or (isinstance(model, str) and not model.strip()):
            model = default_model(name)
        elif not isinstance(model, str) or not 1 <= len(model.strip()) <= 100:
            raise RequestError(400, "invalid_model")
        session.provider = name
        session.model = model.strip()
        self.secrets.set_provider_key(session.session_id, name, key)
        return {"ok": True, "provider": name, "model": session.model, "key_configured": True}

    def clear(self, session: Session) -> dict[str, Any]:
        self.require_local()
        self.secrets.clear_session(session.session_id)
        return {"ok": True, "key_configured": False}

    def complete(
        self, session: Session, messages: list[ChatMessage], *, network_id: str = ""
    ) -> str:
        provider = self.provider
        if provider is None:
            key = self.secrets.get_provider_key(session.session_id, session.provider)
            if key is None:
                raise RequestError(409, "api_key_required")
            provider = create_provider(session.provider, key)
        if (
            self.managed
            and sum(len(item.content) for item in messages) > self.settings.max_context_chars
        ):
            raise RequestError(
                409, "conversation_limit", "This conversation is full. Start over to continue."
            )
        allowance = (
            self.limits.inference(
                session.owner_id or "session:" + session.session_id, network=network_id
            )
            if self.managed
            else nullcontext()
        )
        started = time.monotonic()
        with allowance:
            reply = provider.complete(messages=messages, model=session.model)
        if len(reply) > self.settings.max_context_chars:
            raise ProviderError("The guardian reply was too long. Please try a shorter request.")
        logger.info(
            "event=inference outcome=success latency_ms=%d",
            int((time.monotonic() - started) * 1000),
        )
        return reply
