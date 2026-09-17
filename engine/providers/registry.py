"""Local provider catalog: registration also supplies the browser setup options."""

from collections.abc import Callable
from dataclasses import dataclass

from engine.providers.base import Provider
from engine.providers.deepseek import DeepSeekProvider
from engine.providers.gemini import GeminiProvider
from engine.providers.openai import OpenAIProvider


@dataclass(frozen=True)
class ProviderDefinition:
    label: str
    default_model: str
    factory: Callable[[str], Provider]


PROVIDERS = {
    "gemini": ProviderDefinition("Gemini", "gemini-3.1-flash-lite", GeminiProvider),
    "deepseek": ProviderDefinition("DeepSeek", "deepseek-v4-flash", DeepSeekProvider),
    "openai": ProviderDefinition("OpenAI", "gpt-5.6-luna", OpenAIProvider),
}


def definition(provider: str) -> ProviderDefinition:
    try:
        return PROVIDERS[provider]
    except KeyError:
        raise ValueError(f"Unsupported provider: {provider}") from None


def default_model(provider: str) -> str:
    return definition(provider).default_model


def create_provider(provider: str, api_key: str) -> Provider:
    return definition(provider).factory(api_key)


def catalog() -> dict[str, dict[str, str]]:
    return {
        name: {"label": item.label, "default_model": item.default_model}
        for name, item in PROVIDERS.items()
    }
