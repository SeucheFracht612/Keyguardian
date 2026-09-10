from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from engine.providers.base import ChatMessage, ModelInfo, ProviderError

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_SPECIALIZED_MODEL_MARKERS = (
    "-image",
    "image-generation",
    "-audio",
    "native-audio",
    "-tts",
    "music",
    "lyria",
    "veo",
    "robotics",
    "computer-use",
    "embedding",
)


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

        normalized_model = model.strip().removeprefix("models/")
        url = _BASE_URL.format(model=urllib.parse.quote(normalized_model, safe=""))
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
            raise self._http_error(exc, model=normalized_model) from None
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

    def list_models(self) -> list[ModelInfo]:
        """Return conversational Gemini models suitable for Keyguardian.

        Google's model listing exposes whether a model supports
        ``generateContent`` but does not currently expose one authoritative
        "plain text chat" capability flag. We therefore apply a conservative
        second-stage filter to hide obvious image/audio/music/video/tool-specific
        variants from the normal picker. The UI still has a Custom model option
        for anything intentionally filtered out here.

        Note that Google may list legacy models even when a newer project is not
        entitled to call them. Generation errors are therefore handled separately
        and reported with the useful provider message when available.
        """
        models: list[ModelInfo] = []
        page_token: str | None = None

        while True:
            query = {"pageSize": "1000"}
            if page_token:
                query["pageToken"] = page_token
            url = f"{_MODELS_URL}?{urllib.parse.urlencode(query)}"
            request = urllib.request.Request(
                url,
                method="GET",
                headers={"x-goog-api-key": self._api_key},
            )

            try:
                with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                    body = response.read()
            except urllib.error.HTTPError as exc:
                raise self._http_error(exc) from None
            except urllib.error.URLError:
                raise ProviderError("Could not reach the Gemini API. Check network/proxy access.") from None
            except TimeoutError:
                raise ProviderError("The Gemini model list request timed out.") from None

            try:
                data = json.loads(body.decode("utf-8"))
                raw_models = data.get("models", [])
                for item in raw_models:
                    if not isinstance(item, dict):
                        continue
                    methods = item.get("supportedGenerationMethods", [])
                    if "generateContent" not in methods:
                        continue
                    name = item.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    model_id = name.removeprefix("models/")
                    if not self._is_game_model(model_id):
                        continue
                    display_name = item.get("displayName")
                    label = display_name if isinstance(display_name, str) and display_name else model_id
                    models.append(ModelInfo(id=model_id, label=label))
                page_token = data.get("nextPageToken")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
                raise ProviderError("Gemini returned an unreadable model list.") from None

            if not isinstance(page_token, str) or not page_token:
                break

        unique = {model.id: model for model in models}
        return sorted(unique.values(), key=lambda model: model.id.lower())

    @staticmethod
    def _is_game_model(model_id: str) -> bool:
        normalized = model_id.lower()
        if not normalized.startswith("gemini-"):
            return False
        return not any(marker in normalized for marker in _SPECIALIZED_MODEL_MARKERS)

    @staticmethod
    def _provider_error_message(exc: urllib.error.HTTPError) -> str | None:
        """Extract Google's safe human-readable error without exposing request data."""
        try:
            body = exc.read()
            data = json.loads(body.decode("utf-8"))
            message = data.get("error", {}).get("message")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
            return None
        if not isinstance(message, str):
            return None
        message = " ".join(message.split())
        return message[:500] if message else None

    @classmethod
    def _http_error(
        cls,
        exc: urllib.error.HTTPError,
        *,
        model: str | None = None,
    ) -> ProviderError:
        provider_message = cls._provider_error_message(exc)

        if exc.code == 400:
            message = "Gemini rejected the request configuration."
        elif exc.code in (401, 403):
            message = "Gemini rejected the API key or denied access."
        elif exc.code == 404:
            lowered = provider_message.lower() if provider_message else ""
            if "no longer available to new users" in lowered:
                suffix = f" ({model})" if model else ""
                message = (
                    f"Gemini lists this legacy model{suffix}, but Google does not grant "
                    "generation access to this project. Choose a newer Gemini model."
                )
            elif provider_message:
                message = f"Gemini could not use the selected model: {provider_message}"
            else:
                message = "The configured Gemini resource was not found."
        elif exc.code == 429:
            message = "Gemini rate-limited the request or the project has no available quota."
        else:
            message = f"Gemini request failed with HTTP {exc.code}."

        return ProviderError(message, exc.code)
