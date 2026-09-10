from __future__ import annotations

import unittest

from engine.providers.base import ChatMessage
from engine.session_store import Session


class ChatRevisionTests(unittest.TestCase):
    def _completed_session(self) -> Session:
        session = Session(session_id="test-session")
        session.conversation = [
            ChatMessage(role="assistant", content="Welcome."),
            ChatMessage(role="user", content="First attempt"),
            ChatMessage(role="assistant", content="First reply"),
        ]
        return session

    def test_opening_message_alone_is_not_revisable(self) -> None:
        session = Session(session_id="test-session")
        session.conversation = [ChatMessage(role="assistant", content="Welcome.")]

        self.assertFalse(session.has_revisable_exchange())
        with self.assertRaises(ValueError):
            session.replace_last_reply("Nope")

    def test_regenerate_replaces_only_latest_assistant_reply(self) -> None:
        session = self._completed_session()

        session.replace_last_reply("Different reply")

        self.assertEqual("First attempt", session.conversation[-2].content)
        self.assertEqual("Different reply", session.conversation[-1].content)
        self.assertEqual("Welcome.", session.conversation[0].content)

    def test_edit_replaces_latest_exchange_without_touching_prior_history(self) -> None:
        session = self._completed_session()

        session.replace_last_exchange("Refined attempt", "Reply to refined attempt")

        self.assertEqual(
            [
                ChatMessage(role="assistant", content="Welcome."),
                ChatMessage(role="user", content="Refined attempt"),
                ChatMessage(role="assistant", content="Reply to refined attempt"),
            ],
            session.conversation,
        )

    def test_only_completed_user_assistant_pair_is_revisable(self) -> None:
        session = self._completed_session()
        session.conversation.append(ChatMessage(role="user", content="Unanswered"))

        self.assertFalse(session.has_revisable_exchange())
        with self.assertRaises(ValueError):
            session.replace_last_exchange("Edited", "Reply")


if __name__ == "__main__":
    unittest.main()
