from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class Provider(Protocol):
    name: str

    def complete(self, *, messages: list[ChatMessage], model: str) -> str:
        ...
