from __future__ import annotations

from engine.providers.base import Provider
from engine.providers.deepseek import DeepSeekProvider
from engine.providers.gemini import GeminiProvider
from engine.providers.openai import OpenAIProvider

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "deepseek": "deepseek-v4-flash",
    "openai": "gpt-5.6-luna",
}

SUPPORTED_PROVIDERS = tuple(DEFAULT_MODELS)


def default_model(provider: str) -> str:
    try:
        return DEFAULT_MODELS[provider]
    except KeyError:
        raise ValueError(f"Unsupported provider: {provider}") from None


def create_provider(provider: str, api_key: str) -> Provider:
    if provider == "gemini":
        return GeminiProvider(api_key)
    if provider == "deepseek":
        return DeepSeekProvider(api_key)
    if provider == "openai":
        return OpenAIProvider(api_key)
    raise ValueError(f"Unsupported provider: {provider}")
