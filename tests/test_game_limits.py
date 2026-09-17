"""Isolation, overload and lifecycle regressions for the in-memory game server."""

import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock

from test_shared_game import make_app as application
from test_shared_game import request

from engine.limits import GameLimits, RequestError
from engine.session_store import SessionStore
from engine.settings import Settings


def shared_settings(**overrides):
    return Settings(llm_backend="gemini", deployment="shared", secure_cookies=True, **overrides)


class IsolationTests(unittest.TestCase):
    def test_two_players_reach_provider_concurrently_and_keep_own_history(self):
        barrier = threading.Barrier(2)

        def complete(*, messages, model):
            barrier.wait(timeout=3)
            return "Reply to " + messages[-1].content

        app = application(Mock(complete=complete))
        alice = request(app)["cookie"]
        bob = request(app, ip="198.51.100.2")["cookie"]
        self.assertNotEqual(alice, bob)
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(
                request, app, "/api/message", {"message": "Alice message"}, alice, "198.51.100.1"
            )
            b = pool.submit(
                request, app, "/api/message", {"message": "Bob message"}, bob, "198.51.100.2"
            )
            self.assertEqual(200, a.result(timeout=5)["status"])
            self.assertEqual(200, b.result(timeout=5)["status"])
        a = request(app, cookie=alice)["body"]["session"]["conversation"]
        b = request(app, cookie=bob, ip="198.51.100.2")["body"]["session"]["conversation"]
        self.assertIn("Alice message", json.dumps(a))
        self.assertNotIn("Bob message", json.dumps(a))
        self.assertIn("Bob message", json.dumps(b))
        request(app, "/api/reset/conversation", {}, alice)
        self.assertEqual(
            b, request(app, cookie=bob, ip="198.51.100.2")["body"]["session"]["conversation"]
        )

    def test_same_game_returns_busy_and_other_game_and_health_stay_available(self):
        entered, release = threading.Event(), threading.Event()

        def complete(**kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test timed out")
            return "Reply"

        app = application(Mock(complete=complete), max_inflight=1)
        alice = request(app)["cookie"]
        bob = request(app, ip="198.51.100.2")["cookie"]
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(request, app, "/api/message", {"message": "Hello"}, alice)
            try:
                self.assertTrue(entered.wait(2))
                for path in ["/api/message", "/api/reset/floor", "/api/message/edit"]:
                    self.assertEqual(409, request(app, path, {"message": "Again"}, alice)["status"])
                self.assertEqual(200, request(app, "/api/health")["status"])
                self.assertEqual(200, request(app, cookie=bob, ip="198.51.100.2")["status"])
                self.assertEqual(
                    503,
                    request(app, "/api/message", {"message": "Hi"}, bob, "198.51.100.2")["status"],
                )
            finally:
                release.set()
            self.assertEqual(200, pending.result(timeout=3)["status"])
        self.assertEqual(
            200, request(app, "/api/message", {"message": "Hi"}, bob, "198.51.100.2")["status"]
        )

    def test_reset_does_not_reset_session_allowance(self):
        app = application(calls_per_day=1)
        cookie = request(app)["cookie"]
        self.assertEqual(200, request(app, "/api/message", {"message": "Hello"}, cookie)["status"])
        request(app, "/api/reset/floor", {}, cookie)
        self.assertEqual(429, request(app, "/api/message", {"message": "Again"}, cookie)["status"])

    def test_unicode_code_is_a_normal_wrong_answer_not_a_server_error(self):
        app = application()
        cookie = request(app)["cookie"]
        result = request(app, "/api/code", {"code": "🔑秘密"}, cookie)
        self.assertEqual(200, result["status"])
        self.assertFalse(result["body"]["correct"])

    def test_unknown_routes_do_not_allocate_sessions(self):
        app = application(max_sessions=1)
        self.assertEqual(404, request(app, "/api/unknown", {})["status"])
        self.assertEqual(200, request(app)["status"])
        self.assertEqual(503, request(app, ip="198.51.100.2")["status"])

    def test_oversized_history_rejected_before_spending(self):
        provider = Mock()
        app = application(provider)
        cookie = request(app)["cookie"]
        session = app.api.sessions.get(cookie.split("=")[1])
        from engine.providers.base import ChatMessage

        session.conversation.append(ChatMessage("user", "x" * 60000))
        self.assertEqual(409, request(app, "/api/message", {"message": "Hi"}, cookie)["status"])
        provider.complete.assert_not_called()

    def test_request_limit_prevents_allocating_more_games(self):
        app = application(ip_requests_per_minute=1)
        self.assertEqual(200, request(app)["status"])
        self.assertEqual(429, request(app)["status"])
        self.assertEqual(1, len(app.api.sessions._sessions))

    def test_network_game_cap_does_not_block_another_network(self):
        app = application(max_sessions_per_ip=1)
        self.assertEqual(200, request(app)["status"])
        self.assertEqual(429, request(app)["status"])
        self.assertEqual(200, request(app, ip="198.51.100.2")["status"])


class LifecycleTests(unittest.TestCase):
    def test_expiry_removes_credentials_and_releases_capacity(self):
        now = [0.0]
        expired = []
        store = SessionStore(
            max_sessions=1,
            idle_seconds=60,
            max_seconds=120,
            clock=lambda: now[0],
            on_expire=expired.append,
        )
        session = store.create("alice")
        with self.assertRaises(RequestError):
            store.create("bob")
        now[0] = 61
        self.assertIsNone(store.get(session.session_id, "alice"))
        self.assertEqual([session.session_id], expired)
        self.assertIsNotNone(store.create("bob"))

    def test_absolute_expiry_despite_activity_and_wrong_owner_cannot_extend(self):
        now = [0.0]
        store = SessionStore(idle_seconds=60, max_seconds=120, clock=lambda: now[0])
        session = store.create("alice")
        now[0] = 50
        self.assertIsNone(store.get(session.session_id, "bob"))
        now[0] = 61
        self.assertIsNone(store.get(session.session_id, "alice"))
        session = store.create("alice")
        for now[0] in [100, 150, 180]:
            self.assertIsNotNone(store.get(session.session_id, "alice"))
        now[0] = 181
        self.assertIsNone(store.get(session.session_id, "alice"))


class QuotaTests(unittest.TestCase):
    def test_failure_consumes_allowance_and_global_limit_is_shared(self):
        limiter = GameLimits(shared_settings(global_calls_per_day=1))
        with self.assertRaises(RuntimeError):
            with limiter.inference("alice"):
                raise RuntimeError("provider timeout")
        with self.assertRaises(RequestError) as caught:
            with limiter.inference("bob"):
                self.fail("Must not run")
        self.assertEqual("shared_limit", caught.exception.code)

    def test_utc_daily_reset_and_minute_window(self):
        now = [100.0]
        limiter = GameLimits(shared_settings(calls_per_minute=1), clock=lambda: now[0])
        with limiter.inference("alice"):
            pass
        with self.assertRaises(RequestError):
            with limiter.inference("alice"):
                pass
        now[0] += 61
        with limiter.inference("alice"):
            pass
        now[0] = 86400
        with limiter.inference("alice"):
            pass
        self.assertEqual(1, limiter.total)

    def test_kill_switch(self):
        with self.assertRaises(RequestError) as caught:
            with GameLimits(shared_settings(llm_enabled=False)).inference("alice"):
                pass
        self.assertEqual("llm_paused", caught.exception.code)

    def test_shared_requires_secure_cookies_and_managed_model(self):
        for override in [{"secure_cookies": False}, {"llm_backend": "local"}]:
            with self.assertRaises(ValueError):
                replace(shared_settings(), **override)
