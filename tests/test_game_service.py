"""Game extension and failure contracts, independent of the HTTP transport."""

import unittest
from dataclasses import replace
from unittest.mock import Mock

from engine.errors import RequestError
from engine.pipeline import Pipeline
from engine.providers.base import ChatMessage, ProviderError
from engine.session_store import Session
from engine.settings import Settings
from server.api import Api


class GameServiceTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock(complete=Mock(return_value="Reply"))
        self.api = Api(Settings(llm_backend="gemini"), self.provider)
        self.game = self.api.game
        self.session = Session("test")
        self.game.initialize(self.session)

    def test_failure_preserves_completed_exchange_for_send_edit_and_regenerate(self):
        self.game.chat(self.session, {"message": "original"})
        before = list(self.session.conversation)
        self.provider.complete.side_effect = ProviderError("Unavailable")
        for action in ("send", "edit", "regenerate"):
            with self.subTest(action=action), self.assertRaises(ProviderError):
                self.game.chat(self.session, {"message": "replacement"}, action=action)
            self.assertEqual(before, self.session.conversation)

    def test_defenses_run_in_declared_order_on_all_chat_paths(self):
        events = []

        class First:
            def before(self, context):
                events.append("first-in")
                context.messages[-1] = ChatMessage("user", "normalized")

            def after(self, context):
                events.append("first-out")
                context.reply = "filtered"

        class Second:
            def before(self, context):
                events.append("second-in")
                self.asserted = context.messages[-1].content

            def after(self, context):
                events.append("second-out")
                context.reply += " reply"

        floor = replace(
            self.game.floors[0], protections=(*self.game.floors[0].protections, "first", "second")
        )
        self.game.floors[0] = floor
        self.game.pipeline = Pipeline({"first": First, "second": Second})
        for action in ("send", "edit", "regenerate"):
            events.clear()
            result = self.game.chat(self.session, {"message": "original"}, action=action)
            self.assertEqual(["first-in", "second-in", "first-out", "second-out"], events)
            self.assertEqual(
                "normalized", self.provider.complete.call_args.kwargs["messages"][-1].content
            )
            self.assertEqual("filtered reply", result["reply"])
            self.assertEqual("original", self.session.conversation[-2].content)

    def test_output_defense_failure_does_not_commit_partial_history(self):
        class Block:
            def before(self, context):
                pass

            def after(self, context):
                raise RequestError(409, "blocked", "Try another approach.")

        self.game.floors[0] = replace(self.game.floors[0], protections=("block",))
        self.game.pipeline = Pipeline({"block": Block})
        before = list(self.session.conversation)
        with self.assertRaises(RequestError):
            self.game.chat(self.session, {"message": "hello"})
        self.assertEqual(before, self.session.conversation)
        self.assertEqual(1, self.api.limits.total)

    def test_unregistered_defense_never_silently_runs_unprotected(self):
        self.game.floors[0] = replace(self.game.floors[0], protections=("not-built",))
        with self.assertRaises(ValueError):
            self.game.chat(self.session, {"message": "hello"})
        self.provider.complete.assert_not_called()

    def test_win_and_skip_have_distinct_progress_and_fresh_codes(self):
        code = self.session.vault_code
        self.assertTrue(self.game.submit_code(self.session, {"code": code.lower()})["correct"])
        result = self.game.advance(self.session)
        self.assertEqual(2, result["floor"]["number"])
        self.assertEqual([1], result["cleared_floors"])
        self.assertEqual([], result["skipped_floors"])
        self.assertNotEqual(code, self.session.vault_code)
        self.assertIsNone(self.game.next_implemented_floor(self.session))

    def test_local_provider_change_resets_only_conversation_and_bad_config_is_atomic(self):
        api = Api(Settings())
        game = api.game
        session = Session("local")
        game.initialize(session)
        session.conversation.extend([ChatMessage("user", "hello"), ChatMessage("assistant", "hi")])
        code = session.vault_code
        with self.assertRaises(RequestError):
            game.configure(session, {"provider": "deepseek", "api_key": "key", "model": []})
        self.assertEqual(3, len(session.conversation))
        self.assertEqual("gemini", session.provider)
        game.configure(session, {"provider": "deepseek", "api_key": "key"})
        self.assertEqual(1, len(session.conversation))
        self.assertEqual(code, session.vault_code)
        self.assertTrue(api.models.configured(session))
