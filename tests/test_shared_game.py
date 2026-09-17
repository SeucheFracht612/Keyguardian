import json
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from unittest.mock import Mock, patch

from test_core import _FakeResponse

from engine.limits import RequestError
from engine.providers.base import ChatMessage, ProviderError
from engine.providers.gemini import GeminiProvider
from engine.settings import Settings
from server.api import Api
from server.client_network import ClientNetwork
from server.wsgi import Application


def request(app, path="/api/state", payload=None, cookie="", ip="198.51.100.1", forwarded=None):
    body = b"" if payload is None else json.dumps(payload).encode()
    env = {
        "REQUEST_METHOD": "GET" if payload is None else "POST",
        "PATH_INFO": path,
        "HTTP_HOST": "game.example",
        "HTTP_COOKIE": cookie,
        "REMOTE_ADDR": ip,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/json",
        "wsgi.input": BytesIO(body),
        "wsgi.url_scheme": "http",
        "HTTP_ORIGIN": "https://game.example",
    }
    if forwarded is not None:
        env["HTTP_X_FORWARDED_FOR"] = forwarded
    result = {}

    def start(status, headers):
        result["status"] = int(status.split()[0])
        result["headers"] = dict(headers)

    raw = b"".join(app(env, start))
    result["body"] = json.loads(raw) if raw.startswith(b"{") else raw
    result["cookie"] = result["headers"].get("Set-Cookie", cookie).split(";")[0]
    return result


def make_app(provider=None, **overrides):
    settings = Settings(llm_backend="gemini", deployment="shared", secure_cookies=True, **overrides)
    provider = provider or Mock(complete=Mock(return_value="Hello from the guardian"))
    return Application(Api(settings, provider), ["game.example"])


class AnonymousSharedTests(unittest.TestCase):
    def test_plays_without_login_or_browser_key_and_hides_key_controls(self):
        app = make_app()
        self.assertEqual(200, request(app, "/")["status"])
        state = request(app)
        self.assertEqual("gemini", state["body"]["session"]["provider"])
        self.assertEqual("gemini-3.1-flash-lite", state["body"]["session"]["model"])
        self.assertTrue(state["body"]["capabilities"]["managed_model"])
        cookie = state["cookie"]
        for path, payload in [
            ("/api/message", {"message": "Hi"}),
            ("/api/message/edit", {"message": "Edited"}),
            ("/api/message/regenerate", {}),
        ]:
            self.assertEqual(200, request(app, path, payload, cookie)["status"])
        for path in ["/api/keys", "/api/keys/clear", "/api/models"]:
            self.assertEqual(403, request(app, path, {"api_key": "override"}, cookie)["status"])

    def test_same_office_players_are_independent_and_concurrent(self):
        barrier = threading.Barrier(2)

        def complete(*, messages, model):
            barrier.wait(timeout=3)
            return "Reply: " + messages[-1].content

        app = make_app(Mock(complete=complete))
        a, b = request(app)["cookie"], request(app)["cookie"]
        self.assertNotEqual(a, b)
        with ThreadPoolExecutor(2) as pool:
            futures = [
                pool.submit(request, app, "/api/message", {"message": name}, cookie)
                for name, cookie in [("Alice", a), ("Bob", b)]
            ]
            self.assertEqual([200, 200], [f.result(timeout=5)["status"] for f in futures])
        self.assertNotIn("Bob", json.dumps(request(app, cookie=a)["body"]))
        request(app, "/api/reset/floor", {}, a)
        self.assertIn("Bob", json.dumps(request(app, cookie=b)["body"]))

    def test_new_cookie_and_forged_forwarded_ip_cannot_reset_network_quota(self):
        app = make_app(ip_calls_per_day=1)
        first = request(app)["cookie"]
        self.assertEqual(200, request(app, "/api/message", {"message": "hi"}, first)["status"])
        fresh = request(app, forwarded="203.0.113.99")["cookie"]
        denied = request(app, "/api/message", {"message": "again"}, fresh, forwarded="203.0.113.88")
        self.assertEqual("network_limit", denied["body"]["error"])
        other = request(app, ip="198.51.100.2")["cookie"]
        self.assertEqual(
            200, request(app, "/api/message", {"message": "hi"}, other, ip="198.51.100.2")["status"]
        )

    def test_network_session_capacity_and_request_limit(self):
        app = make_app(max_sessions_per_ip=1)
        first = request(app)["cookie"]
        self.assertEqual(429, request(app)["status"])
        self.assertEqual(200, request(app, cookie=first)["status"])
        self.assertEqual(200, request(app, ip="198.51.100.2")["status"])
        app = make_app(ip_requests_per_minute=1)
        self.assertEqual(200, request(app)["status"])
        self.assertEqual(429, request(app)["status"])
        self.assertEqual(1, len(app.api.sessions._sessions))

    def test_session_survives_network_change_but_retains_session_quota(self):
        app = make_app(calls_per_day=1)
        cookie = request(app)["cookie"]
        self.assertEqual(200, request(app, "/api/message", {"message": "hi"}, cookie)["status"])
        self.assertEqual(200, request(app, cookie=cookie, ip="198.51.100.2")["status"])
        self.assertEqual(
            429,
            request(app, "/api/message", {"message": "again"}, cookie, ip="198.51.100.2")["status"],
        )

    def test_missing_server_key_fails_without_exposing_secret(self):
        settings = Settings(llm_backend="gemini")
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            Api(settings)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "server-key"}):
            api = Api(settings)
            app = Application(api, ["game.example"])
            self.assertNotIn("server-key", json.dumps(request(app)["body"]))
            self.assertNotIn("server-key", repr(settings))


class ProxyTests(unittest.TestCase):
    def test_only_trusted_peer_can_supply_forwarded_ip_and_last_entry_wins(self):
        network = ClientNetwork("10.0.0.0/16")
        direct = network.identify({"REMOTE_ADDR": "198.51.100.1"})
        self.assertEqual(
            direct,
            network.identify(
                {"REMOTE_ADDR": "198.51.100.1", "HTTP_X_FORWARDED_FOR": "203.0.113.9"}
            ),
        )
        self.assertEqual(
            direct,
            network.identify(
                {"REMOTE_ADDR": "10.0.0.4", "HTTP_X_FORWARDED_FOR": "203.0.113.9, 198.51.100.1"}
            ),
        )
        self.assertNotIn("198.51", direct)
        for forwarded in ["", "invalid", "198.51.100.1:1234"]:
            with self.assertRaises(RequestError):
                network.identify({"REMOTE_ADDR": "10.0.0.4", "HTTP_X_FORWARDED_FOR": forwarded})

    def test_ipv6_network_and_mapped_ipv4_normalization(self):
        network = ClientNetwork()
        self.assertEqual(
            network.identify({"REMOTE_ADDR": "2001:db8::1"}),
            network.identify({"REMOTE_ADDR": "2001:db8::2"}),
        )
        self.assertEqual(
            network.identify({"REMOTE_ADDR": "198.51.100.1"}),
            network.identify({"REMOTE_ADDR": "::ffff:198.51.100.1"}),
        )


class ManagedGeminiTests(unittest.TestCase):
    @patch("engine.providers.gemini.urllib.request.urlopen")
    def test_request_mapping_output_limit_and_private_thoughts(self, urlopen):
        urlopen.return_value = _FakeResponse(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [{"text": "private", "thought": True}, {"text": "Hello"}]
                        },
                    }
                ]
            }
        )
        p = GeminiProvider("server-key", managed=True, max_output_tokens=321)
        reply = p.complete(
            model="gemini-3.1-flash-lite",
            messages=[
                ChatMessage("system", "secret rules"),
                ChatMessage("assistant", "Welcome"),
                ChatMessage("user", "Hi"),
            ],
        )
        self.assertEqual("Hello", reply)
        sent = urlopen.call_args.args[0]
        self.assertNotIn("server-key", sent.full_url)
        self.assertIn("gemini-3.1-flash-lite:generateContent", sent.full_url)
        body = json.loads(sent.data)
        self.assertEqual(321, body["generationConfig"]["maxOutputTokens"])
        self.assertEqual(["model", "user"], [m["role"] for m in body["contents"]])

    @patch("engine.providers.gemini.urllib.request.urlopen")
    def test_truncated_response_and_error_body_never_reach_browser(self, urlopen):
        provider = GeminiProvider("secret-key", managed=True)
        urlopen.return_value = _FakeResponse(
            {
                "candidates": [
                    {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}
                ]
            }
        )
        with self.assertRaises(ProviderError):
            provider.complete(model="gemini-3.1-flash-lite", messages=[])
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example", 404, "bad", {}, BytesIO(b'{"error":{"message":"secret-key"}}')
        )
        with self.assertRaises(ProviderError) as caught:
            provider.complete(model="gemini-3.1-flash-lite", messages=[])
        self.assertNotIn("secret-key", str(caught.exception))
