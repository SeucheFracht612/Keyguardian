# Session state is process-local: do not increase workers or application replica count.
import os

bind = "0.0.0.0:" + os.getenv("PORT", "8080")
workers = 1
worker_class = "gthread"
threads = 8
timeout = 120
graceful_timeout = 60
accesslog = None
errorlog = "-"

limit_request_fields = 50
keepalive = 5
max_requests = 0
worker_tmp_dir = "/tmp"


def on_starting(server):
    if server.cfg.workers != 1 or server.cfg.max_requests != 0:
        raise RuntimeError("RAM-only game requires one worker and no worker recycling")
    if server.cfg.threads < 8:
        raise RuntimeError("Use at least eight threads to leave capacity beside inference calls")
