from __future__ import annotations

import threading


class SecretStore:
    """Process-local storage for provider credentials.

    Credentials must never be serialized, logged, returned by the API, or mixed
    into normal session state. Closing the Keyguardian process destroys them.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._provider_keys: dict[tuple[str, str], str] = {}

    def set_provider_key(self, session_id: str, provider: str, api_key: str) -> None:
        with self._lock:
            self._provider_keys[(session_id, provider)] = api_key

    def has_provider_key(self, session_id: str, provider: str) -> bool:
        with self._lock:
            return (session_id, provider) in self._provider_keys

    def get_provider_key(self, session_id: str, provider: str) -> str | None:
        with self._lock:
            return self._provider_keys.get((session_id, provider))

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            stale = [key for key in self._provider_keys if key[0] == session_id]
            for key in stale:
                del self._provider_keys[key]
