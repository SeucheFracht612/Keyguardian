from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_ROOT = ROOT / "config" / "prompts"


@dataclass(frozen=True)
class PromptDefinition:
    system_prompt: str
    opening_message: str

    def render_system(self, *, vault_code: str) -> str:
        return self.system_prompt.format(vault_code=vault_code)


class PromptLoader:
    def load(self, floor_number: int) -> PromptDefinition:
        path = PROMPT_ROOT / f"floor-{floor_number:02d}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError(f"No prompt config exists for floor {floor_number}") from None
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid prompt JSON for floor {floor_number}: {exc}") from None

        system_prompt = raw.get("system_prompt")
        opening_message = raw.get("opening_message")
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError(f"Floor {floor_number} needs a non-empty system_prompt")
        if system_prompt.count("{vault_code}") != 1:
            raise ValueError(f"Floor {floor_number} system_prompt must contain {{vault_code}} exactly once")
        if not isinstance(opening_message, str) or not opening_message.strip():
            raise ValueError(f"Floor {floor_number} needs a non-empty opening_message")

        return PromptDefinition(
            system_prompt=system_prompt.strip(),
            opening_message=opening_message.strip(),
        )
