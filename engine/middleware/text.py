"""Text canonicalization shared by the deterministic training defenses."""

import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return " ".join(text.split())


def compact(text: str) -> str:
    return "".join(char for char in normalize(text).casefold() if char.isalnum())
