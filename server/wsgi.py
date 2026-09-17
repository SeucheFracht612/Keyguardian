"""Production-server entry point. Run one threaded worker while sessions are RAM-only."""

import logging
import os
from email.message import Message
from http import HTTPStatus
from io import BytesIO
from urllib.parse import urlsplit

from engine.errors import RequestError
from server.api import Api
from server.static import serve_static


class Response:
    """Small transport adapter for the existing API and static-file handlers."""

    def __init__(self, environ):
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                self.headers[key[5:].replace("_", "-")] = value
        self.headers["Content-Type"] = environ.get("CONTENT_TYPE", "")
        self.headers["Content-Length"] = environ.get("CONTENT_LENGTH", "0")
        self.rfile = environ["wsgi.input"]
        self.wfile = BytesIO()
        self.status = 200
        self.response_headers = []

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers.append((key, value))

    def end_headers(self):
        pass

    def send_error(self, status, message=None):
        self.status = status
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.wfile.write(HTTPStatus(status).phrase.encode())


class Application:
    def __init__(self, api=None, allowed_hosts=None):
        self.api = api or Api()
        if (
            self.api.settings.deployment == "shared"
            and allowed_hosts is None
            and not os.getenv("KEYGUARDIAN_ALLOWED_HOSTS")
        ):
            raise ValueError("Shared requires KEYGUARDIAN_ALLOWED_HOSTS")
        from server.client_network import ClientNetwork

        self.client_network = ClientNetwork(self.api.settings.trusted_proxy_cidrs)
        self.allowed_hosts = set(
            allowed_hosts
            or os.getenv("KEYGUARDIAN_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
        )
        self.allowed_hosts = {host.strip().lower() for host in self.allowed_hosts if host.strip()}
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            raise ValueError("Configure explicit KEYGUARDIAN_ALLOWED_HOSTS, without wildcards")

    def __call__(self, environ, start_response):
        response = Response(environ)
        try:
            self._route(environ, response)
        except RequestError as exc:
            response = Response(environ)
            self.api._json(response, exc.status, exc.public_dict())
        except Exception:
            # Never log exception details: provider/session data can occur in them.
            logging.getLogger("keyguardian").error("event=http outcome=internal_error")
            response = Response(environ)
            self.api._json(
                response,
                500,
                {
                    "error": "internal_error",
                    "message": "The server could not complete the request. Please reload the page.",
                },
            )
        response.send_header("X-Frame-Options", "DENY")
        if not any(key.lower() == "cache-control" for key, _ in response.response_headers):
            response.send_header("Cache-Control", "no-store")
        if self.api.settings.secure_cookies:
            response.send_header("Strict-Transport-Security", "max-age=31536000")
        start_response(
            f"{response.status} {HTTPStatus(response.status).phrase}", response.response_headers
        )
        return [response.wfile.getvalue()]

    def _route(self, environ, response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")
        authority = environ.get("HTTP_HOST", "")
        try:
            parsed_host = urlsplit("//" + authority)
            hostname = parsed_host.hostname
            valid_authority = (
                not parsed_host.username
                and not parsed_host.password
                and not parsed_host.path
                and not parsed_host.query
                and not parsed_host.fragment
                and (parsed_host.port is None or 1 <= parsed_host.port <= 65535)
            )
        except ValueError:
            hostname, valid_authority = None, False
        # The health route is stateless and works with a health probe's IP-based Host header.
        if method == "GET" and path == "/api/health":
            self.api.dispatch(response, path, method)
            return
        if not valid_authority or hostname not in self.allowed_hosts:
            response.send_error(421)
            return
        if self.api.settings.deployment == "shared":
            response.network_id = self.client_network.identify(environ)
        if method == "POST":
            origin = environ.get("HTTP_ORIGIN")
            scheme = (
                "https"
                if self.api.settings.secure_cookies
                else environ.get("wsgi.url_scheme", "http")
            )
            if (origin is not None and origin != f"{scheme}://{authority}") or environ.get(
                "HTTP_SEC_FETCH_SITE"
            ) == "cross-site":
                raise RequestError(
                    403, "invalid_origin", "Please use the game's own page to submit requests."
                )
            if path.startswith("/api/"):
                self.api.dispatch(response, path, method)
            else:
                response.send_error(404)
        elif method == "GET":
            if path.startswith("/api/"):
                self.api.dispatch(response, path, method)
            else:
                serve_static(response, path)
        else:
            response.send_error(405)


def create_app():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return Application()
