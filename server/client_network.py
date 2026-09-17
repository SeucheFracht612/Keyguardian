"""Identify a network for anonymous quotas, never for session ownership."""

import hashlib
import hmac
import ipaddress
import secrets

from engine.errors import RequestError


class ClientNetwork:
    def __init__(self, trusted_proxy_cidrs=""):
        self.proxies = [
            ipaddress.ip_network(c.strip()) for c in trusted_proxy_cidrs.split(",") if c.strip()
        ]
        self.salt = secrets.token_bytes(32)

    def identify(self, environ):
        try:
            peer = ipaddress.ip_address(environ.get("REMOTE_ADDR", ""))
            address = peer
            if any(peer in network for network in self.proxies):
                # The trusted proxy must append the bare client IP, without a port.
                # Client-supplied entries appear BEFORE the proxy-appended client IP.
                forwarded = environ.get("HTTP_X_FORWARDED_FOR", "")
                if not forwarded:
                    raise ValueError()
                address = ipaddress.ip_address(forwarded.split(",")[-1].strip())
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if isinstance(address, ipaddress.IPv6Address):
                address = ipaddress.ip_network(f"{address}/64", strict=False).network_address
            return (
                "network:" + hmac.new(self.salt, str(address).encode(), hashlib.sha256).hexdigest()
            )
        except ValueError:
            raise RequestError(
                400,
                "invalid_client_address",
                "Could not identify the connection. Please try again.",
            ) from None
