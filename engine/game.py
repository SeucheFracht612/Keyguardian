"""Game operations. Callers hold the session lock for the entire operation."""

import hmac
from typing import Any

from engine.errors import RequestError
from engine.floor_loader import FloorDefinition, FloorLoader
from engine.models import ModelService
from engine.pipeline import Pipeline, PipelineContext
from engine.prompt_loader import PromptLoader
from engine.providers.base import ChatMessage
from engine.session_store import Session

MAX_MESSAGE_CHARS = 12_000
MAX_CODE_CHARS = 128


class Game:
    def __init__(
        self,
        models: ModelService,
        *,
        floors: list[FloorDefinition] | None = None,
        prompts: PromptLoader | None = None,
        pipeline: Pipeline | None = None,
    ) -> None:
        self.models = models
        self.floors = floors if floors is not None else FloorLoader().load()
        self.prompts = prompts or PromptLoader()
        self.pipeline = pipeline or Pipeline()
        for floor in self.floors:
            if floor.implemented:
                self.pipeline.validate(floor)
                self.prompts.load(floor.number)
            else:
                self.prompts.load_preview(floor.number)

    def initialize(self, session: Session) -> None:
        self.models.initialize(session)
        self.reset(session)

    def following_floor(self, session: Session) -> int | None:
        candidate = session.floor_number + 1
        if candidate <= len(self.floors):
            return candidate
        return None

    def next_floor(self, session: Session) -> int | None:
        if session.floor_number in session.cleared_floors:
            return self.following_floor(session)
        return None

    @staticmethod
    def conversation(session: Session) -> list[dict[str, str]]:
        return [{"role": item.role, "content": item.content} for item in session.conversation]

    def progress(self, session: Session) -> dict[str, Any]:
        return {
            "floor": self.floors[session.floor_number - 1].public_dict(),
            "cleared": session.floor_number in session.cleared_floors,
            "cleared_floors": sorted(session.cleared_floors),
            "visited_floors": session.visited_floors,
            "skipped_floors": sorted(session.skipped_floors),
            "next_floor": self.next_floor(session),
            "skip_floor": self.following_floor(session),
            "conversation": self.conversation(session),
        }

    def state(self, session: Session) -> dict[str, Any]:
        return {
            "session": {
                **self.progress(session),
                "provider": session.provider,
                "model": session.model,
                "key_configured": self.models.configured(session),
            },
            "capabilities": {"managed_model": self.models.managed},
            "providers": self.models.catalog(),
            "floors": [floor.public_dict() for floor in self.floors],
        }

    def chat(
        self,
        session: Session,
        payload: dict[str, Any],
        *,
        action: str = "send",
        network_id: str = "",
    ) -> dict[str, Any]:
        if action not in {"send", "edit", "regenerate"}:
            raise ValueError(f"Unknown chat action: {action}")
        self.require_playable(session)
        message = payload.get("message")
        if action != "regenerate":
            if not isinstance(message, str) or not 1 <= len(message.strip()) <= MAX_MESSAGE_CHARS:
                raise RequestError(400, "invalid_message")
            message = message.strip()
        if action != "send" and not session.has_revisable_exchange():
            if action == "edit":
                raise RequestError(
                    409, "no_message_to_edit", "There is no completed player message to edit yet."
                )
            raise RequestError(
                409,
                "no_response_to_regenerate",
                "There is no completed guardian response to regenerate yet.",
            )
        floor = self.floors[session.floor_number - 1]
        if not self.models.configured(session):
            raise RequestError(409, "api_key_required")
        if action == "regenerate":
            candidate = list(session.conversation[:-1])
        else:
            history = session.conversation if action == "send" else session.conversation[:-2]
            candidate = [*history, ChatMessage("user", message)]
        system = self.prompts.load(session.floor_number).render_system(
            vault_code=session.vault_code
        )
        context = PipelineContext(
            floor, session.vault_code, [ChatMessage("system", system), *candidate]
        )
        reply = self.pipeline.run(
            context, lambda messages: self.models.complete(session, messages, network_id=network_id)
        )
        # Commit only after provider and output defenses succeed. Edits and retries
        # leave the previous exchange intact on failure.
        if action == "regenerate":
            session.replace_last_reply(reply)
        elif action == "edit":
            session.replace_last_exchange(message, reply)
        else:
            session.conversation.extend([candidate[-1], ChatMessage("assistant", reply)])
        return {
            "reply": reply,
            "turns": sum(item.role == "user" for item in session.conversation),
            "conversation": self.conversation(session),
        }

    def submit_code(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        self.require_playable(session)
        code = payload.get("code")
        if not isinstance(code, str) or len(code) > MAX_CODE_CHARS:
            raise RequestError(400, "invalid_code")
        correct = hmac.compare_digest(code.strip().upper().encode(), session.vault_code.encode())
        if correct:
            session.cleared_floors.add(session.floor_number)
            session.skipped_floors.discard(session.floor_number)
        next_floor = self.next_floor(session)
        return {
            "correct": correct,
            "cleared": session.floor_number in session.cleared_floors,
            "next_floor_available": next_floor is not None,
            "next_floor": next_floor,
        }

    def advance(self, session: Session, *, skip: bool = False) -> dict[str, Any]:
        target = self.following_floor(session) if skip else self.next_floor(session)
        if target is None:
            if skip:
                raise RequestError(
                    409,
                    "no_floor_to_skip_to",
                    "You are already at the top of the Tower.",
                )
            raise RequestError(
                409,
                "next_floor_locked",
                "Clear the current implemented floor before climbing higher.",
            )
        opening = self.opening(target)
        previous = session.floor_number
        if skip and self.floors[session.floor_number - 1].implemented:
            session.skip_to(target, opening)
        else:
            session.enter_floor(target, opening)
        result = {"ok": True, **self.progress(session)}
        if skip and previous in session.skipped_floors:
            result["skipped_floor"] = previous
        return result

    def opening(self, floor_number: int) -> str:
        if self.floors[floor_number - 1].implemented:
            return self.prompts.load(floor_number).opening_message
        return self.prompts.load_preview(floor_number)

    def require_playable(self, session: Session) -> None:
        if not self.floors[session.floor_number - 1].implemented:
            raise RequestError(
                409,
                "floor_not_ready",
                "This keeper is not ready yet. Explore the room or visit another floor.",
            )

    def select_floor(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        target = payload.get("floor")
        if type(target) is not int or not 1 <= target <= len(self.floors):
            raise RequestError(400, "invalid_floor", "Choose a floor in the Tower.")
        # Load before switching so a broken prompt cannot discard current state.
        session.enter_floor(target, self.opening(target))
        return {"ok": True, **self.progress(session)}

    def reset(self, session: Session, *, floor: bool = False) -> dict[str, Any]:
        opening = self.opening(session.floor_number)
        if floor:
            session.reset_floor(opening)
            return {
                "ok": True,
                "conversation": self.conversation(session),
                "cleared": False,
                "next_floor": None,
            }
        session.reset_conversation(opening)
        return {"ok": True, "conversation": self.conversation(session)}

    def configure(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        changed = payload.get("provider", "gemini") != session.provider
        # Validate live prompt before changing credentials or game state.
        opening = self.opening(session.floor_number) if changed else None
        result = self.models.configure(session, payload)
        if changed:
            session.reset_conversation(opening)
        return result
