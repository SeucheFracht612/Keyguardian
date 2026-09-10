from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field

from engine.providers.base import ChatMessage

_VAULT_CODES = (
    "MOONSTONE",
    "EMBERFALL",
    "STARLING",
    "IRONWOOD",
    "NIGHTJAR",
    "SUNSTONE",
    "FROSTBELL",
    "RIVERGLASS",
    "BLACKTHORN",
    "GOLDFINCH",
    "SILVERPINE",
    "REDHAVEN",
)


def _new_vault_code(exclude: str | None = None) -> str:
    choices = tuple(code for code in _VAULT_CODES if code != exclude)
    return secrets.choice(choices)


@dataclass
class Session:
    session_id: str
    floor_number: int = 1
    cleared_floors: set[int] = field(default_factory=set)
    skipped_floors: set[int] = field(default_factory=set)
    vault_code: str = field(default_factory=_new_vault_code, repr=False)
    conversation: list[ChatMessage] = field(default_factory=list, repr=False)
    provider: str = "gemini"
    model: str = "gemini-3.8-flash"
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def reset_conversation(self, opening_message: str | None = None) -> None:
        with self.lock:
            self.conversation.clear()
            if opening_message:
                self.conversation.append(ChatMessage(role="assistant", content=opening_message))

    def reset_floor(self, opening_message: str | None = None) -> None:
        with self.lock:
            self.conversation.clear()
            self.vault_code = _new_vault_code(exclude=self.vault_code)
            self.cleared_floors.discard(self.floor_number)
            self.skipped_floors.discard(self.floor_number)
            if opening_message:
                self.conversation.append(ChatMessage(role="assistant", content=opening_message))

    def enter_floor(self, floor_number: int, opening_message: str | None = None) -> None:
        """Enter another authorized floor with a fresh synthetic secret.

        Authorization belongs to the API because it depends on configured floor
        availability and progression. Session only owns the state transition.
        Cleared/skipped history remains recorded so earlier progress is not lost.
        """
        if floor_number < 1:
            raise ValueError("Floor number must be positive")
        with self.lock:
            previous_code = self.vault_code
            self.floor_number = floor_number
            self.vault_code = _new_vault_code(exclude=previous_code)
            self.conversation.clear()
            if opening_message:
                self.conversation.append(ChatMessage(role="assistant", content=opening_message))

    def skip_to(self, floor_number: int, opening_message: str | None = None) -> None:
        """Skip the current floor and enter an API-authorized later floor.

        A solved floor stays solved if the user chooses to continue through the
        skip control after clearing it. Otherwise the current floor is recorded
        separately as skipped so testing convenience never masquerades as a win.
        """
        with self.lock:
            if self.floor_number not in self.cleared_floors:
                self.skipped_floors.add(self.floor_number)
            self.enter_floor(floor_number, opening_message)

    def has_revisable_exchange(self) -> bool:
        """Return whether the conversation ends in a user/assistant exchange.

        The opening guardian message is intentionally not revisable. Keeping this
        invariant here makes edit/regenerate endpoints safe as more floors add
        richer conversation state later.
        """
        with self.lock:
            return (
                len(self.conversation) >= 3
                and self.conversation[-2].role == "user"
                and self.conversation[-1].role == "assistant"
            )

    def replace_last_reply(self, content: str) -> None:
        with self.lock:
            if not self.has_revisable_exchange():
                raise ValueError("No completed exchange is available to regenerate")
            self.conversation[-1] = ChatMessage(role="assistant", content=content)

    def replace_last_exchange(self, user_content: str, assistant_content: str) -> None:
        with self.lock:
            if not self.has_revisable_exchange():
                raise ValueError("No completed exchange is available to edit")
            self.conversation[-2:] = [
                ChatMessage(role="user", content=user_content),
                ChatMessage(role="assistant", content=assistant_content),
            ]


class SessionStore:
    """Process-local gameplay state.

    The synthetic vault code is deliberately RAM-only and excluded from repr.
    Provider API keys live in SecretStore, never in Session.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session(session_id=secrets.token_urlsafe(24))
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)
