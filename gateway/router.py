"""Explicit heuristic, not a semantic complexity classifier."""


def choose_model(message: str, settings) -> str:
    markers = ("почему", "объясни", "расскажи историю", "план")
    if len(message) > 200 or any(m in message.casefold() for m in markers):
        return settings.strong_model
    return settings.cheap_model
