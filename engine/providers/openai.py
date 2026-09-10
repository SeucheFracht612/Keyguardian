from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from engine.providers.base import ChatMessage

_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass
class ProviderError(Exception):
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


class OpenAIProvider:
    """Small stdlib-only OpenAI Responses API adapter."""

    name = "openai"

    def __init__(self, api_key: str, *, timeout_seconds: float = 45.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def complete(self, *, messages: list[ChatMessage], model: str) -> str:
        payload = {
            "model": model,
            "input": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "max_output_tokens": 800,
        }
        request = urllib.request.Request(
            _RESPONSES_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            # Never propagate request headers or a raw provider response into logs/UI.
            if exc.code == 401:
                message = "OpenAI rejected the API key."
            elif exc.code == 403:
                message = "OpenAI denied access to this request or model."
            elif exc.code == 429:
                message = "OpenAI rate-limited the request. Try again shortly."
            else:
                message = f"OpenAI request failed with HTTP {exc.code}."
            raise ProviderError(message, exc.code) from None
        except urllib.error.URLError:
            raise ProviderError("Could not reach the OpenAI API.") from None
        except TimeoutError:
            raise ProviderError("The OpenAI request timed out.") from None

        try:
            data = json.loads(body.decode("utf-8"))
            text_parts: list[str] = []
            for item in data.get("output", []):
                if item.get("type") != "message":
                    continue
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)
            text = "".join(text_parts).strip()
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
            raise ProviderError("OpenAI returned an unreadable response.") from None

        if not text:
            raise ProviderError("OpenAI returned no assistant text.")
        return text
