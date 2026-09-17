from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from engine.errors import RequestError
from engine.providers.base import ChatMessage
from engine.providers.registry import default_model

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
class FloorState:
    vault_code: str = field(repr=False)
    conversation: list[ChatMessage] = field(default_factory=list, repr=False)


@dataclass
class Session:
    session_id: str
    owner_id: str = field(default="", repr=False)
    network_id: str = field(default="", repr=False)
    created_at: float = field(default_factory=time.monotonic, repr=False)
    last_seen: float = field(default_factory=time.monotonic, repr=False)
    floor_number: int = 1
    cleared_floors: set[int] = field(default_factory=set)
    skipped_floors: set[int] = field(default_factory=set)
    vault_code: str = field(default_factory=_new_vault_code, repr=False)
    conversation: list[ChatMessage] = field(default_factory=list, repr=False)
    _visited: dict[int, FloorState] = field(default_factory=dict, repr=False)
    provider: str = "gemini"
    model: str = field(default_factory=lambda: default_model("gemini"))
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
        """Save the current room and resume a visited room, or create its first state.

        The active room lives in the public session fields; _visited holds only
        inactive rooms. Inactive rooms and codes are never serialized into API state.
        """
        if floor_number < 1:
            raise ValueError("Floor number must be positive")
        with self.lock:
            if floor_number == self.floor_number:
                return
            self._visited[self.floor_number] = FloorState(self.vault_code, self.conversation)
            target = self._visited.pop(floor_number, None)
            if target is None:
                target = FloorState(_new_vault_code(exclude=self.vault_code))
                if opening_message:
                    target.conversation.append(ChatMessage("assistant", opening_message))
            self.floor_number = floor_number
            self.vault_code = target.vault_code
            self.conversation = target.conversation

    @property
    def visited_floors(self) -> list[int]:
        return sorted({self.floor_number, *self._visited})

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

    def __init__(
        self,
        *,
        max_sessions=200,
        idle_seconds=3600,
        max_seconds=28800,
        on_expire=None,
        clock=time.monotonic,
        max_per_owner=5,
        max_per_network=50,
    ) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}
        self.max_sessions = max_sessions
        self.max_per_owner = max_per_owner
        self.max_per_network = max_per_network
        self.idle_seconds = idle_seconds
        self.max_seconds = max_seconds
        self.on_expire = on_expire or (lambda session_id: None)
        self.clock = clock

    def _expired(self, session, now):
        return (
            now - session.last_seen >= self.idle_seconds
            or now - session.created_at >= self.max_seconds
        )

    def _prune(self, now):
        for session_id, session in list(self._sessions.items()):
            if self._expired(session, now) and session.lock.acquire(blocking=False):
                try:
                    del self._sessions[session_id]
                    self.on_expire(session_id)
                finally:
                    session.lock.release()

    def create(self, owner_id="", network_id="") -> Session:
        with self._lock:
            now = self.clock()
            self._prune(now)
            if len(self._sessions) >= self.max_sessions:
                raise RequestError(
                    503, "session_capacity", "All game spaces are occupied. Please try later."
                )
            if (
                owner_id
                and sum(s.owner_id == owner_id for s in self._sessions.values())
                >= self.max_per_owner
            ):
                raise RequestError(
                    429,
                    "player_session_limit",
                    "You have several games open. Use an existing game or wait for an old game to expire.",
                )
            if (
                network_id
                and sum(s.network_id == network_id for s in self._sessions.values())
                >= self.max_per_network
            ):
                raise RequestError(
                    429,
                    "network_session_limit",
                    "Too many games are open on this network. Use an existing game or try later.",
                )
            session = Session(
                session_id=secrets.token_urlsafe(24),
                owner_id=owner_id,
                network_id=network_id,
                created_at=now,
                last_seen=now,
            )
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str, owner_id="") -> Session | None:
        with self._lock:
            now = self.clock()
            self._prune(now)
            session = self._sessions.get(session_id)
            if session is None or session.owner_id != owner_id or self._expired(session, now):
                return None
            session.last_seen = now
            return session
