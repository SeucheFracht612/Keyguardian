from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from engine.providers.base import ChatMessage, ProviderError

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider:
    """Stdlib-only Gemini generateContent adapter.

    Keyguardian keeps conversation state locally and sends the full history on
    each call, so the stateless generateContent endpoint is sufficient here.
    """

    name = "gemini"

    def __init__(self, api_key: str, *, timeout_seconds: float = 45.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def complete(self, *, messages: list[ChatMessage], model: str) -> str:
        system_parts: list[str] = []
        contents: list[dict[str, object]] = []

        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": message.content}],
                }
            )

        payload: dict[str, object] = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 1200},
        }
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }

        url = _BASE_URL.format(model=urllib.parse.quote(model, safe=""))
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                message = "Gemini rejected the request configuration."
            elif exc.code in (401, 403):
                message = "Gemini rejected the API key or denied access to this model."
            elif exc.code == 404:
                message = "The configured Gemini model was not found."
            elif exc.code == 429:
                message = "Gemini rate-limited the request or the project has no available quota."
            else:
                message = f"Gemini request failed with HTTP {exc.code}."
            raise ProviderError(message, exc.code) from None
        except urllib.error.URLError:
            raise ProviderError("Could not reach the Gemini API. Check network/proxy access.") from None
        except TimeoutError:
            raise ProviderError("The Gemini request timed out.") from None

        try:
            data = json.loads(body.decode("utf-8"))
            candidates = data["candidates"]
            parts = candidates[0]["content"]["parts"]
            text = "".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ).strip()
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, AttributeError, TypeError):
            raise ProviderError("Gemini returned an unreadable response.") from None

        if not text:
            raise ProviderError("Gemini returned no assistant text.")
        return text
