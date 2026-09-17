"""Provider-independent HTTP and managed-model contracts."""

import json
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from engine.providers.base import ProviderError
from engine.settings import Settings
from server.api import Api
from server.wsgi import Application


class HostedFlowTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock()
        self.provider.complete.return_value = "Guardian reply"
        self.api = Api(Settings(llm_backend="gemini", secure_cookies=True), self.provider)
        self.app = Application(self.api, ["game.example"])
        self.cookie = ""

    def request(self, path, payload=None, host="game.example", origin=None):
        data = json.dumps(payload).encode() if payload is not None else b""
        environ = {
            "REQUEST_METHOD": "POST" if payload is not None else "GET",
            "PATH_INFO": path,
            "HTTP_HOST": host,
            "HTTP_COOKIE": self.cookie,
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(data)),
            "wsgi.input": BytesIO(data),
            "wsgi.url_scheme": "http",
        }
        if origin:
            environ["HTTP_ORIGIN"] = origin
        result = {}

        def start(status, headers):
            result["status"] = int(status.split()[0])
            result["headers"] = dict(headers)

        body = b"".join(self.app(environ, start))
        if "Set-Cookie" in result["headers"]:
            self.cookie = result["headers"]["Set-Cookie"].split(";")[0]
        result["body"] = json.loads(body) if body.startswith(b"{") else body
        return result

    def test_managed_chat_edit_regenerate_and_reset(self):
        state = self.request("/api/state")
        self.assertTrue(state["body"]["capabilities"]["managed_model"])
        self.assertTrue(state["body"]["session"]["key_configured"])
        self.assertIn("Secure", state["headers"]["Set-Cookie"])
        self.assertNotIn("vault_code", state["body"]["session"])
        for path, body in [
            ("/api/message", {"message": "hi"}),
            ("/api/message/edit", {"message": "edited"}),
            ("/api/message/regenerate", {}),
        ]:
            self.assertEqual(200, self.request(path, body)["status"])
        self.assertEqual(3, self.provider.complete.call_count)
        state = self.request("/api/state")["body"]["session"]
        self.assertEqual(3, len(state["conversation"]))
        self.assertEqual("edited", state["conversation"][1]["content"])
        self.assertEqual(200, self.request("/api/reset/conversation", {})["status"])
        self.assertEqual(1, len(self.request("/api/state")["body"]["session"]["conversation"]))

    def test_failure_does_not_change_history(self):
        before = self.request("/api/state")["body"]["session"]["conversation"]
        self.provider.complete.side_effect = ProviderError("unavailable")
        self.assertEqual(502, self.request("/api/message", {"message": "hi"})["status"])
        self.assertEqual(before, self.request("/api/state")["body"]["session"]["conversation"])

    def test_managed_settings_cannot_be_overridden(self):
        for path in ["/api/keys", "/api/keys/clear", "/api/models"]:
            self.assertEqual(
                403, self.request(path, {"provider": "openai", "api_key": "bad"})["status"]
            )
        self.assertEqual(
            self.api.settings.gemini_model, self.request("/api/state")["body"]["session"]["model"]
        )

    def test_origin_host_and_health_boundaries(self):
        self.assertEqual(421, self.request("/api/state", host="evil.example")["status"])
        self.assertEqual(
            403, self.request("/api/message", {}, origin="https://evil.example")["status"]
        )
        self.assertEqual(200, self.request("/api/health", host="10.0.0.2:8080")["status"])
        self.assertEqual(
            200,
            self.request("/api/reset/conversation", {}, origin="https://game.example")["status"],
        )
        self.assertEqual(200, self.request("/")["status"])
        self.assertEqual(403, self.request("/../app.py")["status"])

    def test_local_mode_still_requires_player_key(self):
        self.api = Api(Settings())
        self.app = Application(self.api, ["game.example"])
        self.assertFalse(self.request("/api/state")["body"]["capabilities"]["managed_model"])
        self.assertEqual(409, self.request("/api/message", {"message": "hi"})["status"])


class SettingsTests(unittest.TestCase):
    def test_unsupported_backend_is_rejected(self):
        with patch.dict("os.environ", {"KEYGUARDIAN_LLM_BACKEND": "unknown"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_local_mode_needs_no_environment_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual("local", Settings.from_env().llm_backend)
