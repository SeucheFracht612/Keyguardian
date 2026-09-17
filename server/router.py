"""Threaded loopback server using the same WSGI application as Gunicorn."""

from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from engine.settings import Settings
from server.api import Api
from server.wsgi import Application


class LocalServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class LocalHandler(WSGIRequestHandler):
    def log_message(self, fmt, *args):
        # Avoid request paths: users may put sensitive values in query strings.
        pass


def build_server(host: str, port: int, *, api: Api | None = None) -> WSGIServer:
    if host != "127.0.0.1":
        raise ValueError("Keyguardian must bind to 127.0.0.1 only")
    settings = api.settings if api is not None else Settings.from_env()
    if settings.deployment == "shared":
        raise ValueError("Shared mode must run through Gunicorn, not the local server")
    application = Application(api or Api(settings), ["localhost", "127.0.0.1"])
    return make_server(
        host, port, application, server_class=LocalServer, handler_class=LocalHandler
    )
