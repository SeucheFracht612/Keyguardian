"""Static assets shared by local and hosted transports."""

import mimetypes
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


def serve_static(response, path: str) -> None:
    relative = "index.html" if path in ("", "/") else path.lstrip("/")
    target = (WEB_ROOT / relative).resolve()

    try:
        target.relative_to(WEB_ROOT.resolve())
    except ValueError:
        response.send_error(403)
        return

    if not target.is_file():
        response.send_error(404)
        return

    content_type, _ = mimetypes.guess_type(str(target))
    data = target.read_bytes()
    response.send_response(200)
    response.send_header("Content-Type", content_type or "application/octet-stream")
    response.send_header("Content-Length", str(len(data)))
    response.send_header("Cache-Control", "no-store")
    response.send_header("X-Content-Type-Options", "nosniff")
    response.send_header("Referrer-Policy", "no-referrer")
    response.send_header("Cross-Origin-Resource-Policy", "same-origin")
    response.send_header(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'",
    )
    response.end_headers()
    response.wfile.write(data)
