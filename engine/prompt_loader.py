from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_ROOT = ROOT / "config" / "prompts"
SHARED_PROMPT_PATH = PROMPT_ROOT / "shared.json"


@dataclass(frozen=True)
class PromptDefinition:
    floor_number: int
    warden_name: str
    shared_system_prompt: str
    floor_system_prompt: str
    opening_message: str

    def render_system(self, *, vault_code: str) -> str:
        floor_prompt = self.floor_system_prompt.replace("{vault_code}", vault_code)
        return (
            self.shared_system_prompt
            .replace("{warden_name}", self.warden_name)
            .replace("{floor_number}", str(self.floor_number))
            .replace("{floor_prompt}", floor_prompt)
        )


class PromptLoader:
    """Load live-editable shared lore plus one floor-specific prompt.

    Files are intentionally read on every call so prompt authors can tune copy
    while the local server is running. The shared prompt owns world knowledge
    and character conventions; floor prompts remain the sole source of gameplay
    secrecy rules.
    """

    def load(self, floor_number: int) -> PromptDefinition:
        shared = self._load_json(SHARED_PROMPT_PATH, "shared prompt")
        floor_path = PROMPT_ROOT / f"floor-{floor_number:02d}.json"
        floor = self._load_json(floor_path, f"floor {floor_number} prompt")

        shared_system_prompt = shared.get("system_prompt")
        if not isinstance(shared_system_prompt, str) or not shared_system_prompt.strip():
            raise ValueError("Shared prompt needs a non-empty system_prompt")

        for placeholder in ("{warden_name}", "{floor_number}", "{floor_prompt}"):
            if shared_system_prompt.count(placeholder) != 1:
                raise ValueError(
                    f"Shared system_prompt must contain {placeholder} exactly once"
                )
        if "{vault_code}" in shared_system_prompt:
            raise ValueError(
                "Shared system_prompt must not contain {vault_code}; secret handling belongs to floor prompts"
            )

        warden_name = floor.get("warden_name")
        system_prompt = floor.get("system_prompt")
        opening_message = floor.get("opening_message")

        if not isinstance(warden_name, str) or not warden_name.strip():
            raise ValueError(f"Floor {floor_number} needs a non-empty warden_name")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError(f"Floor {floor_number} needs a non-empty system_prompt")
        if system_prompt.count("{vault_code}") != 1:
            raise ValueError(
                f"Floor {floor_number} system_prompt must contain {{vault_code}} exactly once"
            )
        if "{floor_prompt}" in system_prompt:
            raise ValueError(
                f"Floor {floor_number} system_prompt must not contain {{floor_prompt}}"
            )
        if not isinstance(opening_message, str) or not opening_message.strip():
            raise ValueError(f"Floor {floor_number} needs a non-empty opening_message")

        return PromptDefinition(
            floor_number=floor_number,
            warden_name=warden_name.strip(),
            shared_system_prompt=shared_system_prompt.strip(),
            floor_system_prompt=system_prompt.strip(),
            opening_message=opening_message.strip(),
        )

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, object]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError(f"No {label} config exists at {path}") from None
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {label}: {exc}") from None

        if not isinstance(raw, dict):
            raise ValueError(f"{label.capitalize()} must be a JSON object")
        return raw
