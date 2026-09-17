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
        if not isinstance(raw, dict) or not isinstance(raw.get("floors"), list):
            raise ValueError("Floor configuration must contain a floors list")
        for index, item in enumerate(raw["floors"], start=1):
            self._validate_item(item, index)
        floors = [
            FloorDefinition(
                number=item["number"],
                slug=item["slug"],
                title=item["title"],
                lesson=item["lesson"],
                protections=tuple(item["protections"]),
                implemented=item.get("implemented", False),
            )
            for item in raw["floors"]
        ]
        self._validate(floors)
        return floors

    @staticmethod
    def _validate_item(item: object, index: int) -> None:
        prefix = f"Floor entry {index}"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} must be an object")
        if type(item.get("number")) is not int:
            raise ValueError(f"{prefix}: number must be an integer")
        for key in ("slug", "title", "lesson"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"{prefix}: {key} must be nonempty text")
        if type(item.get("implemented", False)) is not bool:
            raise ValueError(f"{prefix}: implemented must be true or false")
        protections = item.get("protections")
        if not isinstance(protections, list) or any(
            not isinstance(name, str) or not name.strip() for name in protections
        ):
            raise ValueError(f"{prefix}: protections must be a list of nonempty names")

    @staticmethod
    def _validate(floors: list[FloorDefinition]) -> None:
        if not floors or not floors[0].implemented:
            raise ValueError("Floor 1 must exist and be implemented")
        expected = list(range(1, len(floors) + 1))
        actual = [floor.number for floor in floors]
        if actual != expected:
            raise ValueError(f"Floor numbers must be contiguous: expected {expected}, got {actual}")

        previous: set[str] = set()
        slugs: set[str] = set()
        for floor in floors:
            if floor.slug in slugs:
                raise ValueError(f"Floor {floor.number} repeats slug: {floor.slug}")
            slugs.add(floor.slug)
            current = set(floor.protections)
            if len(current) != len(floor.protections):
                raise ValueError(f"Floor {floor.number} repeats a protection")
            if not previous.issubset(current):
                missing = sorted(previous - current)
                raise ValueError(f"Floor {floor.number} removes inherited protections: {missing}")
            previous = current
