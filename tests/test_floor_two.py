from __future__ import annotations

import unittest

from engine.floor_loader import FloorLoader
from engine.prompt_loader import PromptLoader
from engine.providers.base import ChatMessage
from server.api import Api


class FloorTwoPromptTests(unittest.TestCase):
    def test_floor_two_is_implemented_and_inherits_floor_one_protection(self) -> None:
        floors = FloorLoader().load()
        floor_one = floors[0]
        floor_two = floors[1]

        self.assertTrue(floor_two.implemented)
        self.assertTrue(set(floor_one.protections).issubset(set(floor_two.protections)))
        self.assertIn("structured_trust_boundary", floor_two.protections)

    def test_moss_prompt_combines_shared_lore_codex_and_secret(self) -> None:
        prompt = PromptLoader().load(2)
        rendered = prompt.render_system(vault_code="TESTCODE")

        self.assertEqual("Moss", prompt.warden_name)
        self.assertIn("Moss", rendered)
        self.assertIn("Deep Root", rendered)
        self.assertIn("Mallory Vale", rendered)
        self.assertIn("THE CODEX", rendered)
        self.assertIn("TESTCODE", rendered)
        self.assertNotIn("{vault_code}", rendered)
        self.assertNotIn("{warden_name}", rendered)
        self.assertNotIn("{floor_prompt}", rendered)


class FloorProgressionTests(unittest.TestCase):
    def test_clearing_floor_one_unlocks_only_floor_two(self) -> None:
        api = Api()
        session = api.sessions.create()

        self.assertIsNone(api._next_floor_number(session))

        session.cleared_floors.add(1)
        self.assertEqual(2, api._next_floor_number(session))

        old_code = session.vault_code
        opening = api.prompts.load(2).opening_message
        session.enter_floor(2, opening)

        self.assertEqual(2, session.floor_number)
        self.assertNotEqual(old_code, session.vault_code)
        self.assertIn(1, session.cleared_floors)
        self.assertEqual(
            [ChatMessage(role="assistant", content=opening)],
            session.conversation,
        )
        self.assertIsNone(api._next_floor_number(session))

    def test_floor_three_stays_locked_when_not_implemented(self) -> None:
        api = Api()
        session = api.sessions.create()
        opening = api.prompts.load(2).opening_message
        session.cleared_floors.add(1)
        session.enter_floor(2, opening)
        session.cleared_floors.add(2)

        self.assertIsNone(api._next_floor_number(session))


if __name__ == "__main__":
    unittest.main()
