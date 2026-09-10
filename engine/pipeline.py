from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from engine.floor_loader import FloorDefinition


@dataclass
class PipelineContext:
    session_id: str
    floor: FloorDefinition
    user_message: str
    metadata: dict[str, object] = field(default_factory=dict)


class Middleware(Protocol):
    name: str

    def process(self, context: PipelineContext) -> PipelineContext:
        ...


class Pipeline:
    """Ordered defense pipeline for one floor.

    Floors describe protections; the pipeline builder will later map those
    protection identifiers to concrete middleware. Keeping this abstraction
    now prevents floor-specific branches from leaking into the API layer.
    """

    def __init__(self, middleware: list[Middleware] | None = None) -> None:
        self.middleware = middleware or []

    def run(self, context: PipelineContext) -> PipelineContext:
        for layer in self.middleware:
            context = layer.process(context)
        return context
