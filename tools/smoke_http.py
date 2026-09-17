"""Read-only local HTTP smoke test; does not make an LLM call."""

import argparse
import json
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    args = parser.parse_args()
    for path in ["/api/health", "/api/state", "/"]:
        with urllib.request.urlopen(args.base_url.rstrip("/") + path, timeout=5) as response:
            assert response.status == 200, path
            if path.startswith("/api/"):
                payload = json.load(response)
                assert isinstance(payload, dict), path
        print(f"PASS {path}")


if __name__ == "__main__":
    main()
