"""Bounded, process-local shared quotas; resetting a game does not reset these."""

import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field

from engine.errors import RequestError


@dataclass
class Usage:
    requests: deque = field(default_factory=deque)
    calls: deque = field(default_factory=deque)
    daily_calls: int = 0


class GameLimits:
    def __init__(self, settings, clock=time.time):
        self.settings = settings
        self.clock = clock
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(settings.max_inflight)
        self.day = int(clock() // 86400)
        self.owners = {}
        self.total = 0

    def _usage(self, owner):
        now = self.clock()
        day = int(now // 86400)
        if day != self.day:
            self.owners.clear()
            self.total = 0
            self.day = day
        if owner not in self.owners:
            if len(self.owners) >= 5000:
                raise RequestError(
                    503, "capacity", "The game server is at capacity. Please try later."
                )
            self.owners[owner] = Usage()
        usage = self.owners[owner]
        for queue in (usage.requests, usage.calls):
            while queue and queue[0] <= now - 60:
                queue.popleft()
        return now, usage

    def request(self, owner, limit=None):
        with self.lock:
            now, usage = self._usage(owner)
            if len(usage.requests) >= (
                limit if limit is not None else self.settings.requests_per_minute
            ):
                raise RequestError(429, "request_limit", "Too many requests. Please wait a minute.")
            usage.requests.append(now)

    @contextmanager
    def inference(self, owner, network=None):
        if not self.settings.llm_enabled:
            raise RequestError(
                503, "llm_paused", "The guardian service is paused by the administrator."
            )
        if not self.slots.acquire(blocking=False):
            raise RequestError(
                503, "guardian_busy", "The guardians are busy. Please try again shortly."
            )
        try:
            with self.lock:
                now, usage = self._usage(owner)
                if (
                    len(usage.calls) >= self.settings.calls_per_minute
                    or usage.daily_calls >= self.settings.calls_per_day
                ):
                    raise RequestError(
                        429,
                        "player_limit",
                        "Your guardian request limit has been reached. Please try later.",
                    )
                network_usage = None
                if network:
                    _, network_usage = self._usage(network)
                    if (
                        len(network_usage.calls) >= self.settings.ip_calls_per_minute
                        or network_usage.daily_calls >= self.settings.ip_calls_per_day
                    ):
                        raise RequestError(
                            429,
                            "network_limit",
                            "This network's guardian request allowance has been reached. Please try later.",
                        )
                if self.total >= self.settings.global_calls_per_day:
                    raise RequestError(
                        429, "shared_limit", "Today's server request allowance has been reached."
                    )
                usage.calls.append(now)
                usage.daily_calls += 1
                if network_usage is not None:
                    network_usage.calls.append(now)
                    network_usage.daily_calls += 1
                self.total += 1
            # Failed and uncertain provider calls still consume the reserved allowance.
            yield
        finally:
            self.slots.release()
