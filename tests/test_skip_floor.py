from __future__ import annotations

import unittest

from engine.providers.base import ChatMessage
from server.api import Api


class SkipFloorTests(unittest.TestCase):
    def test_floor_one_can_skip_to_implemented_floor_two(self) -> None:
        api = Api()
        session = api.sessions.create()
        old_code = session.vault_code
        opening = api.prompts.load(2).opening_message

        self.assertEqual(2, api._next_implemented_floor_number(session))

        session.skip_to(2, opening)

        self.assertEqual(2, session.floor_number)
        self.assertIn(1, session.skipped_floors)
        self.assertNotIn(1, session.cleared_floors)
        self.assertNotEqual(old_code, session.vault_code)
        self.assertEqual(
            [ChatMessage(role="assistant", content=opening)],
            session.conversation,
        )

    def test_cleared_floor_is_not_relabelled_as_skipped(self) -> None:
        api = Api()
        session = api.sessions.create()
        session.cleared_floors.add(1)
        opening = api.prompts.load(2).opening_message

        session.skip_to(2, opening)

        self.assertIn(1, session.cleared_floors)
        self.assertNotIn(1, session.skipped_floors)

    def test_last_implemented_floor_has_no_skip_target(self) -> None:
        api = Api()
        session = api.sessions.create()
        session.skip_to(2, api.prompts.load(2).opening_message)

        self.assertIsNone(api._next_implemented_floor_number(session))

    def test_reset_current_floor_clears_current_skip_marker(self) -> None:
        api = Api()
        session = api.sessions.create()
        session.skipped_floors.add(1)

        session.reset_floor(api.prompts.load(1).opening_message)

        self.assertNotIn(1, session.skipped_floors)


if __name__ == "__main__":
    unittest.main()
