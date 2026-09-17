"""Exercise the real local transport and the WSGI request boundary."""

import json
import threading
import unittest
from http.client import HTTPConnection

from engine.settings import Settings
from server.api import Api
from server.router import build_server


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = Api(Settings())
        cls.server = build_server("127.0.0.1", 0, api=cls.api)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, *, method="GET", body=None, headers=None):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            client.request(method, path, body=body, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def test_serves_native_modules_with_javascript_mime_and_same_csp(self):
        for path in (
            "/",
            "/app.js",
            "/provider-setup.js",
            "/conversation-view.js",
            "/floor-view.js",
        ):
            status, headers, body = self.request(path)
            self.assertEqual(200, status, path)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            if path.endswith(".js"):
                self.assertIn("javascript", headers["Content-Type"])
            else:
                self.assertIn(b'type="module"', body)

    def test_local_host_origin_and_method_checks_match_hosted_boundary(self):
        self.assertEqual(421, self.request("/api/state", headers={"Host": "evil.example"})[0])
        self.assertEqual(
            403,
            self.request(
                "/api/reset/floor",
                method="POST",
                body="{}",
                headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
            )[0],
        )
        self.assertEqual(405, self.request("/api/state", method="OPTIONS")[0])
        self.assertEqual(403, self.request("/../app.py")[0])

    def test_bad_json_returns_400_and_cookie_is_reusable(self):
        status, headers, body = self.request(
            "/api/message",
            method="POST",
            body="not-json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(400, status)
        cookie = headers["Set-Cookie"].split(";")[0]
        self.assertEqual("bad_request", json.loads(body)["error"])
        self.assertEqual(200, self.request("/api/state", headers={"Cookie": cookie})[0])

    def test_state_includes_configured_floor_catalog_and_no_secret(self):
        status, headers, body = self.request("/api/state")
        data = json.loads(body)
        self.assertEqual(200, status)
        self.assertEqual([f.public_dict() for f in self.api.game.floors], data["floors"])
        self.assertNotIn("vault_code", data["session"])
        session_id = headers["Set-Cookie"].split(";")[0].split("=")[1]
        self.assertNotIn(self.api.sessions.get(session_id).vault_code.encode(), body)
