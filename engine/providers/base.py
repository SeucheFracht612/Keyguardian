from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str

    def public_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label}


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

    def list_models(self) -> list[ModelInfo]:
        ...
