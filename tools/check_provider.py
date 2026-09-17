"""Validate Gemini configuration; --invoke makes one explicitly requested billed API call."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.providers.base import ChatMessage, ProviderError
from engine.providers.gemini import GeminiProvider
from engine.settings import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--invoke", action="store_true", help="Send one short request to Gemini; may incur charges."
    )
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if settings.llm_backend != "gemini":
            raise ValueError("Set KEYGUARDIAN_LLM_BACKEND=gemini")
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key or len(key) > 2048 or any(c.isspace() for c in key):
            raise ValueError("Set GEMINI_API_KEY securely in your environment")
        provider = GeminiProvider(key, managed=True, max_output_tokens=256)
        print("PASS Gemini configuration (key validity and model access not yet tested)")
        if args.invoke:
            provider.complete(
                model=settings.gemini_model,
                messages=[ChatMessage("user", "Reply with just: ready")],
            )
            print("PASS Gemini returned a complete text reply")
        else:
            print("No network call made. --invoke tests the key/model with one billed request.")
    except (ValueError, ProviderError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
