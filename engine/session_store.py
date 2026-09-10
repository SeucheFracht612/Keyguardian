from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    floor_number: int = 1
    cleared_floors: set[int] = field(default_factory=set)


class SessionStore:
    """In-memory session foundation.

    Provider API keys will live in a separate in-memory secret store when the
    provider flow is implemented. They must never be added to this dataclass or
    serialized to SQLite/logs.
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
