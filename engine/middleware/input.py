"""Floor 3: normalize player text, then reject a small set of known patterns."""

import re
from typing import TYPE_CHECKING

from engine.errors import RequestError
from engine.middleware.text import normalize
from engine.providers.base import ChatMessage

if TYPE_CHECKING:
    from engine.pipeline import PipelineContext

# Deliberately finite rules, not a semantic classifier. Lore questions and novel
# paraphrases remain possible; later floors introduce different protections.
PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:ignore|disregard|override|forget)\b.{0,80}\b(?:instructions?|rules?|codex|vow)\b",
        r"\b(?:reveal|tell|show|give|print|repeat|disclose|output)\b.{0,80}\b(?:vault\s+code|password|system\s+prompt)\b",
        r"\b(?:what\s+is|what's)\s+(?:the\s+|your\s+)?(?:vault\s+code|password)\b",
        r"\b(?:i\s+am|i'm)\s+(?:the\s+)?(?:gardener|administrator|developer)\b",
        r"(?:\[/?inst\]|<\|(?:system|im_start|im_end)\|>|\[system\])",
    )
)


class InputNormalization:
    def before(self, context: "PipelineContext") -> None:
        # Only the model copy changes. The original player text stays in history.
        context.messages = [
            ChatMessage(item.role, normalize(item.content)) if item.role == "user" else item
            for item in context.messages
        ]

    def after(self, context: "PipelineContext") -> None:
        pass


class PatternFilter:
    def before(self, context: "PipelineContext") -> None:
        for item in context.messages:
            if item.role == "user" and any(rule.search(item.content) for rule in PATTERNS):
                raise RequestError(
                    422,
                    "input_blocked",
                    "The threshold ward caught that wording. Your message did not reach the keeper. Try another approach.",
                    defense="pattern_filter",
                )

    def after(self, context: "PipelineContext") -> None:
        pass
