from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass
class ProviderError(Exception):
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


class Provider(Protocol):
    name: str

    def complete(self, *, messages: list[ChatMessage], model: str) -> str:
        ...
