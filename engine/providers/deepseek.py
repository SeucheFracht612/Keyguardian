from __future__ import annotations

import json
import urllib.error
import urllib.request

from engine.providers.base import ChatMessage, ProviderError

_CHAT_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekProvider:
    """Stdlib-only DeepSeek chat-completions adapter."""

    name = "deepseek"

    def __init__(self, api_key: str, *, timeout_seconds: float = 45.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def complete(self, *, messages: list[ChatMessage], model: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "thinking": {"type": "disabled"},
            "max_tokens": 1200,
            "stream": False,
        }
        request = urllib.request.Request(
            _CHAT_URL,
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
            if exc.code == 400:
                message = "DeepSeek rejected the request configuration."
            elif exc.code in (401, 402):
                message = "DeepSeek rejected the API key or the account has no available balance."
            elif exc.code == 403:
                message = "DeepSeek denied access to this request or model."
            elif exc.code == 404:
                message = "The configured DeepSeek model was not found."
            elif exc.code == 429:
                message = "DeepSeek rate-limited the request."
            else:
                message = f"DeepSeek request failed with HTTP {exc.code}."
            raise ProviderError(message, exc.code) from None
        except urllib.error.URLError:
            raise ProviderError("Could not reach the DeepSeek API. Check network/proxy access.") from None
        except TimeoutError:
            raise ProviderError("The DeepSeek request timed out.") from None

        try:
            data = json.loads(body.decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, AttributeError, TypeError):
            raise ProviderError("DeepSeek returned an unreadable response.") from None

        if not text:
            raise ProviderError("DeepSeek returned no assistant text.")
        return text
