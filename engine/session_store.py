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
    vault_code: str = field(default_factory=_new_vault_code, repr=False)
    conversation: list[ChatMessage] = field(default_factory=list, repr=False)
    provider: str = "openai"
    model: str = "gpt-5.6-luna"
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def reset_conversation(self) -> None:
        with self.lock:
            self.conversation.clear()

    def reset_floor(self) -> None:
        with self.lock:
            self.conversation.clear()
            self.vault_code = _new_vault_code(exclude=self.vault_code)
            self.cleared_floors.discard(self.floor_number)


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
