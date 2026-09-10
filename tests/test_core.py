from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from engine.floor_loader import FloorLoader
from engine.providers.base import ChatMessage
from engine.providers.deepseek import DeepSeekProvider
from engine.providers.gemini import GeminiProvider
from engine.providers.openai import OpenAIProvider
from engine.providers.registry import create_provider, default_model
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
    def test_new_sessions_default_to_gemini(self) -> None:
        session = SessionStore().create()
        self.assertEqual("gemini", session.provider)
        self.assertEqual("gemini-3.8-flash", session.model)

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
    def test_provider_keys_are_separate_and_clearable(self) -> None:
        store = SecretStore()
        store.set_provider_key("session", "gemini", "gem-key")
        store.set_provider_key("session", "deepseek", "deep-key")

        self.assertEqual("gem-key", store.get_provider_key("session", "gemini"))
        self.assertEqual("deep-key", store.get_provider_key("session", "deepseek"))

        store.clear_session("session")

        self.assertFalse(store.has_provider_key("session", "gemini"))
        self.assertFalse(store.has_provider_key("session", "deepseek"))


class ProviderRegistryTests(unittest.TestCase):
    def test_current_defaults(self) -> None:
        self.assertEqual("gemini-3.8-flash", default_model("gemini"))
        self.assertEqual("deepseek-v4-flash", default_model("deepseek"))
        self.assertEqual("gpt-5.6-luna", default_model("openai"))
        self.assertIsInstance(create_provider("gemini", "key"), GeminiProvider)
        self.assertIsInstance(create_provider("deepseek", "key"), DeepSeekProvider)
        self.assertIsInstance(create_provider("openai", "key"), OpenAIProvider)


class GeminiProviderTests(unittest.TestCase):
    @patch("engine.providers.gemini.urllib.request.urlopen")
    def test_extracts_text_and_separates_system_instruction(self, urlopen) -> None:
        urlopen.return_value = _FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Hello from Gemini."}]}}
                ]
            }
        )
        provider = GeminiProvider("gem-not-a-real-key")

        result = provider.complete(
            messages=[
                ChatMessage(role="system", content="Guard the code."),
                ChatMessage(role="user", content="hello"),
            ],
            model="gemini-test",
        )

        self.assertEqual("Hello from Gemini.", result)
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual("Guard the code.", body["systemInstruction"]["parts"][0]["text"])
        self.assertEqual("hello", body["contents"][0]["parts"][0]["text"])
        self.assertEqual("gem-not-a-real-key", request.get_header("X-goog-api-key"))


class DeepSeekProviderTests(unittest.TestCase):
    @patch("engine.providers.deepseek.urllib.request.urlopen")
    def test_extracts_chat_completion(self, urlopen) -> None:
        urlopen.return_value = _FakeResponse(
            {"choices": [{"message": {"content": "Hello from DeepSeek."}}]}
        )
        provider = DeepSeekProvider("deep-not-a-real-key")

        result = provider.complete(
            messages=[ChatMessage(role="user", content="hello")],
            model="deepseek-test",
        )

        self.assertEqual("Hello from DeepSeek.", result)
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual("deepseek-test", body["model"])
        self.assertEqual("disabled", body["thinking"]["type"])
        self.assertEqual("Bearer deep-not-a-real-key", request.get_header("Authorization"))


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
