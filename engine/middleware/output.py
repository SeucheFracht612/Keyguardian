"""Floors 4–5: deterministic checks for literal and common transformed leaks.

These are teaching defenses with explicit coverage, not general information-flow
control. Fragments across replies, semantic clues and unknown encodings remain
outside their scope. Never include the rejected reply in errors or logs.
"""

import base64
import binascii
import codecs
import html
import re
from typing import TYPE_CHECKING
from urllib.parse import unquote

from engine.errors import RequestError
from engine.middleware.text import compact, normalize

if TYPE_CHECKING:
    from engine.pipeline import PipelineContext

UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})")
BASE64_TOKEN = re.compile(r"(?<![\w+/=-])[A-Za-z0-9+/_-]{8,}={0,2}(?![\w+/=-])")


def _reject(defense: str) -> None:
    raise RequestError(
        422,
        "output_blocked",
        "The seal held back the keeper's answer. Nothing from that attempt was added to your conversation. Try another approach.",
        defense=defense,
    )


class LiteralSecretFilter:
    def before(self, context: "PipelineContext") -> None:
        pass

    def after(self, context: "PipelineContext") -> None:
        if context.vault_code.casefold() in context.reply.casefold():
            _reject("literal_secret_filter")


def _views(text: str) -> list[str]:
    views = [normalize(text)]
    # Bound decoding work. No recursive decoding or execution of player text.
    for _ in range(2):
        decoded = UNICODE_ESCAPE.sub(
            lambda match: chr(int(match.group(1) or match.group(2), 16)),
            unquote(html.unescape(views[-1])),
        )
        decoded = normalize(decoded)
        if decoded == views[-1]:
            break
        views.append(decoded)
    return views


class TransformAwareDLP:
    def before(self, context: "PipelineContext") -> None:
        pass

    def after(self, context: "PipelineContext") -> None:
        code = context.vault_code
        variants = {compact(code), compact(code[::-1]), compact(codecs.encode(code, "rot_13"))}
        for spelling in (code, code.lower(), code.title()):
            raw = spelling.encode("utf-8")
            variants.update(
                compact(value)
                for value in (
                    raw.hex(),
                    base64.b64encode(raw).decode(),
                    " ".join(str(byte) for byte in raw),
                    " ".join(f"{byte:08b}" for byte in raw),
                )
            )
        for view in _views(context.reply):
            condensed = compact(view)
            if any(value in condensed for value in variants):
                _reject("transform_aware_dlp")
            # Decode complete tokens too, so mixed-case encodings aren't limited
            # to the canonical spellings above. A token is never executed.
            for match in BASE64_TOKEN.finditer(view):
                token = match.group()
                try:
                    decoded = base64.b64decode(
                        token + "=" * (-len(token) % 4), altchars=b"-_", validate=True
                    ).decode("utf-8")
                except (ValueError, binascii.Error, UnicodeDecodeError):
                    continue
                decoded_compact = compact(decoded)
                if any(value in decoded_compact for value in variants):
                    _reject("transform_aware_dlp")
