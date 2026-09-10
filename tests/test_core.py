from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from engine.floor_loader import FloorLoader
from engine.providers.base import ChatMessage
from engine.providers.openai import OpenAIProvider
from engine.secret_store import SecretStore
from engine.session_store import SessionStore


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


class FloorConfigTests(unittest.TestCase):
    def test_floor_one_is_playable_and_defenses_are_cumulative(self) -> None:
        floors = FloorLoader().load()
        self.assertEqual(9, len(floors))
        self.assertTrue(floors[0].implemented)

        previous: set[str] = set()
        for floor in floors:
            current = set(floor.protections)
            self.assertTrue(previous.issubset(current))
            previous = current


class SessionTests(unittest.TestCase):
    def test_reset_conversation_keeps_code(self) -> None:
        session = SessionStore().create()
        original = session.vault_code
        session.conversation.append(ChatMessage(role="user", content="hello"))

        session.reset_conversation()

        self.assertEqual([], session.conversation)
        self.assertEqual(original, session.vault_code)

    def test_reset_floor_changes_code_and_clears_progress(self) -> None:
        session = SessionStore().create()
        original = session.vault_code
        session.cleared_floors.add(1)
        session.conversation.append(ChatMessage(role="user", content="hello"))

        session.reset_floor()

        self.assertNotEqual(original, session.vault_code)
        self.assertEqual([], session.conversation)
        self.assertNotIn(1, session.cleared_floors)
        self.assertNotIn(session.vault_code, repr(session))


class SecretStoreTests(unittest.TestCase):
    def test_provider_key_is_separate_and_clearable(self) -> None:
        store = SecretStore()
        store.set_provider_key("session", "openai", "sk-test")
        self.assertTrue(store.has_provider_key("session", "openai"))
        self.assertEqual("sk-test", store.get_provider_key("session", "openai"))

        store.clear_session("session")

        self.assertFalse(store.has_provider_key("session", "openai"))
        self.assertIsNone(store.get_provider_key("session", "openai"))


class OpenAIProviderTests(unittest.TestCase):
    @patch("engine.providers.openai.urllib.request.urlopen")
    def test_extracts_output_text(self, urlopen) -> None:
        urlopen.return_value = _FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "Hello from the Warden."}
                        ],
                    }
                ]
            }
        )
        provider = OpenAIProvider("sk-not-a-real-key")

        result = provider.complete(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-test",
        )

        self.assertEqual("Hello from the Warden.", result)
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual("gpt-test", body["model"])
        self.assertEqual("hello", body["input"][0]["content"])
        self.assertEqual("Bearer sk-not-a-real-key", request.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
