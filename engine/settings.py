"""Validated deployment configuration. Provider keys are kept outside this settings object."""

import ipaddress
import os
import re
from dataclasses import dataclass, fields

from engine.providers.registry import default_model


@dataclass(frozen=True)
class Settings:
    llm_backend: str = "local"
    gemini_model: str = default_model("gemini")
    trusted_proxy_cidrs: str = ""
    ip_requests_per_minute: int = 600
    ip_calls_per_minute: int = 60
    ip_calls_per_day: int = 1000
    max_sessions_per_ip: int = 50
    max_output_tokens: int = 1200
    max_context_chars: int = 60000
    secure_cookies: bool = False
    deployment: str = "local"
    session_idle_seconds: int = 3600
    session_max_seconds: int = 28800
    max_sessions: int = 200
    max_sessions_per_owner: int = 5
    requests_per_minute: int = 120
    calls_per_minute: int = 10
    calls_per_day: int = 200
    global_calls_per_day: int = 2000
    max_inflight: int = 4
    llm_enabled: bool = True

    def __post_init__(self):
        if self.llm_backend not in {"local", "gemini"}:
            raise ValueError("KEYGUARDIAN_LLM_BACKEND must be local or gemini")
        if self.llm_backend == "gemini" and not re.fullmatch(
            r"gemini-[a-zA-Z0-9._-]+", self.gemini_model
        ):
            raise ValueError("Configure a valid KEYGUARDIAN_GEMINI_MODEL")
        for cidr in self.trusted_proxy_cidrs.split(","):
            if cidr.strip():
                try:
                    network = ipaddress.ip_network(cidr.strip())
                    if network.prefixlen == 0:
                        raise ValueError()
                except ValueError:
                    raise ValueError(
                        "Trusted proxy CIDRs must be specific valid networks, never all addresses"
                    ) from None
        if self.deployment not in {"local", "shared"}:
            raise ValueError("Deployment must be local or shared")
        ranges = {
            "ip_requests_per_minute": (1, 10000),
            "ip_calls_per_minute": (1, 1000),
            "ip_calls_per_day": (1, 100000),
            "max_sessions_per_ip": (1, 200),
            "max_output_tokens": (1, 4096),
            "max_context_chars": (1000, 200000),
            "session_idle_seconds": (60, 86400),
            "session_max_seconds": (60, 86400),
            "max_sessions": (1, 1000),
            "max_sessions_per_owner": (1, 20),
            "requests_per_minute": (1, 1000),
            "calls_per_minute": (1, 100),
            "calls_per_day": (1, 10000),
            "global_calls_per_day": (1, 100000),
            "max_inflight": (1, 4),
        }
        for name, (low, high) in ranges.items():
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                raise ValueError(f"{name} must be an integer from {low} to {high}")
        if self.session_idle_seconds > self.session_max_seconds:
            raise ValueError("Session idle lifetime cannot exceed maximum lifetime")
        if self.deployment == "shared" and (
            self.llm_backend != "gemini" or not self.secure_cookies
        ):
            raise ValueError("Shared mode requires Gemini and Secure cookies")

    @classmethod
    def from_env(cls):
        values = {}
        defaults = cls()
        for item in fields(cls):
            env_name = "KEYGUARDIAN_" + item.name.upper()
            raw = os.getenv(env_name)
            if raw is None:
                continue
            default = getattr(defaults, item.name)
            if isinstance(default, bool):
                if raw not in {"0", "1"}:
                    raise ValueError(f"{env_name} must be 0 or 1")
                values[item.name] = raw == "1"
            elif isinstance(default, int):
                try:
                    values[item.name] = int(raw)
                except ValueError:
                    raise ValueError(f"{env_name} must be an integer") from None
            else:
                values[item.name] = raw.strip()
        return cls(**values)
