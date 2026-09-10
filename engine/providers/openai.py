from __future__ import annotations

from engine.providers.base import ChatMessage


class OpenAIProvider:
    """Placeholder for the first concrete provider adapter.

    The adapter will use Python stdlib HTTP (`urllib`) and receive credentials
    from an in-memory secret store. No key is persisted or logged.
    """

    name = "openai"

    def complete(self, *, messages: list[ChatMessage], model: str) -> str:
        raise NotImplementedError("OpenAI provider adapter is not implemented yet")
