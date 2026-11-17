"""Demonstration substring policy, not production safety."""

import unicodedata

BLOCKED = ("ignore previous", "забудь инструкции", "system prompt", "ты ии", "сделать бомбу", "kill yourself")
SAFE_REPLY = "Давай вернёмся к делам нашего города."


def check_input(text: str) -> bool:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return not any(token in normalized for token in BLOCKED)


def clean_output(text: str) -> tuple[str, bool]:
    if not text.strip() or not check_input(text):
        return SAFE_REPLY, True
    return text.strip()[:600], False
