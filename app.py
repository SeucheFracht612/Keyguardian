from __future__ import annotations

import os
import threading
import webbrowser

from server.router import build_server

HOST = "127.0.0.1"
PORT = 8765


def main() -> None:
    server = build_server(HOST, PORT)
    url = f"http://{HOST}:{PORT}"

    if os.environ.get("KEYGUARDIAN_NO_BROWSER") != "1":
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()

    print(f"Keyguardian running at {url}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Keyguardian.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
