"""Floor-selected defenses. Prompt-only protections require no runtime filter."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from engine.floor_loader import FloorDefinition
from engine.middleware.input import InputNormalization, PatternFilter
from engine.middleware.output import LiteralSecretFilter, TransformAwareDLP
from engine.providers.base import ChatMessage

PROMPT_PROTECTIONS = frozenset({"system_secrecy_rule", "structured_trust_boundary"})


@dataclass
class PipelineContext:
    floor: FloorDefinition
    vault_code: str = field(repr=False)
    messages: list[ChatMessage] = field(repr=False)
    reply: str = field(default="", repr=False)


class Defense(Protocol):
    def before(self, context: PipelineContext) -> None: ...
    def after(self, context: PipelineContext) -> None: ...


# Add factories here when implementing runtime protections for later floors.
# Each request gets fresh instances; do not store player state in this registry.
DEFENSES: dict[str, Callable[[], Defense]] = {
    "input_normalization": InputNormalization,
    "pattern_filter": PatternFilter,
    "literal_secret_filter": LiteralSecretFilter,
    "transform_aware_dlp": TransformAwareDLP,
}


class Pipeline:
    def __init__(self, factories: Mapping[str, Callable[[], Defense]] | None = None) -> None:
        self.factories = dict(DEFENSES if factories is None else factories)

    def validate(self, floor: FloorDefinition) -> None:
        missing = set(floor.protections) - PROMPT_PROTECTIONS - self.factories.keys()
        if missing:
            raise ValueError(
                f"Floor {floor.number} has unimplemented defenses: {', '.join(sorted(missing))}"
            )

    def run(self, context: PipelineContext, complete: Callable[[list[ChatMessage]], str]) -> str:
        self.validate(context.floor)
        layers = [
            self.factories[name]() for name in context.floor.protections if name in self.factories
        ]
        for layer in layers:
            layer.before(context)
        context.reply = complete(context.messages)
        for layer in layers:
            layer.after(context)
        return context.reply
