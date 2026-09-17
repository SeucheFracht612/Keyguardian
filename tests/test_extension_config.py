"""Configuration mistakes and provider additions must fail or propagate predictably."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engine.errors import RequestError
from engine.floor_loader import FloorLoader
from engine.providers.registry import PROVIDERS, ProviderDefinition, create_provider
from engine.session_store import Session
from engine.settings import Settings
from server.api import Api


class ExtensionConfigTests(unittest.TestCase):
    def load(self, entries):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "floors.json"
            path.write_text(json.dumps({"floors": entries}), encoding="utf-8")
            return FloorLoader(path).load()

    def test_invalid_floor_fields_report_the_field(self):
        floor = FloorLoader().load()[0].public_dict()
        for field, value in (
            ("number", True),
            ("implemented", "false"),
            ("protections", "system_secrecy_rule"),
            ("protections", [{}]),
            ("title", " "),
        ):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                self.load([{**floor, field: value}])

    def test_duplicate_slugs_are_rejected_and_previews_do_not_lock_later_floors(self):
        floors = [item.public_dict() for item in FloorLoader().load()]
        floors[1]["slug"] = floors[0]["slug"]
        with self.assertRaisesRegex(ValueError, "repeats slug"):
            self.load(floors)
        floors[1]["slug"] = "second"
        floors[1]["implemented"] = False
        floors[2]["implemented"] = True
        loaded = self.load(floors)
        self.assertFalse(loaded[1].implemented)
        self.assertTrue(loaded[2].implemented)

    def test_registration_supplies_state_configuration_and_factory(self):
        factory = Mock()
        entry = ProviderDefinition("Example", "example-model", factory)
        with patch.dict(PROVIDERS, example=entry):
            api = Api(Settings())
            session = Session("extension")
            api.game.initialize(session)
            self.assertEqual(
                {"label": "Example", "default_model": "example-model"},
                api.game.state(session)["providers"]["example"],
            )
            api.game.configure(session, {"provider": "example", "api_key": "test-key"})
            self.assertEqual("example-model", session.model)
            create_provider(session.provider, "test-key")
            factory.assert_called_once_with("test-key")

    def test_malformed_provider_names_are_client_errors(self):
        api = Api(Settings())
        for name in ([], {}, None, 123, "missing"):
            with self.subTest(name=name), self.assertRaises(RequestError) as caught:
                api.models.list_models({"provider": name, "api_key": "test-key"})
            self.assertEqual(400, caught.exception.status)
