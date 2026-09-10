from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "floors.json"


@dataclass(frozen=True)
class FloorDefinition:
    number: int
    slug: str
    title: str
    lesson: str
    protections: tuple[str, ...]
    implemented: bool

    def public_dict(self) -> dict[str, object]:
        return {
            "number": self.number,
            "slug": self.slug,
            "title": self.title,
            "lesson": self.lesson,
            "protections": list(self.protections),
            "implemented": self.implemented,
        }


class FloorLoader:
    def __init__(self, path: Path = DEFAULT_CONFIG) -> None:
        self.path = path

    def load(self) -> list[FloorDefinition]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        floors = [
            FloorDefinition(
                number=item["number"],
                slug=item["slug"],
                title=item["title"],
                lesson=item["lesson"],
                protections=tuple(item["protections"]),
                implemented=bool(item.get("implemented", False)),
            )
            for item in raw["floors"]
        ]
        self._validate(floors)
        return floors

    @staticmethod
    def _validate(floors: list[FloorDefinition]) -> None:
        expected = list(range(1, len(floors) + 1))
        actual = [floor.number for floor in floors]
        if actual != expected:
            raise ValueError(f"Floor numbers must be contiguous: expected {expected}, got {actual}")

        previous: set[str] = set()
        for floor in floors:
            current = set(floor.protections)
            if not previous.issubset(current):
                missing = sorted(previous - current)
                raise ValueError(
                    f"Floor {floor.number} removes inherited protections: {missing}"
                )
            previous = current
