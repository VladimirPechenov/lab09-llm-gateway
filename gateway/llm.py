"""Bounded retries, independent fallback and explicit offline mode."""

import time
from dataclasses import dataclass

import httpx

PERSONAS = {
    "trader": "Ты - торговец Барт, жадный и весёлый. Отвечай кратко, в роли.",
    "guard": "Ты - стражница Ирма, строгая. Отвечай кратко, в роли.",
}


@dataclass
class Result:
    reply: str
    model: str
    attempts: int
    degraded: bool


def call(settings, model: str, npc: str, message: str) -> str:
    system = PERSONAS[npc]
    if settings.provider == "mock":
        time.sleep(min(settings.mock_delay, settings.timeout))
        if settings.mock_delay > settings.timeout:
            raise TimeoutError("mock timeout")
        if npc == "trader":
            return "Лечебное зелье стоит двадцать монет, путник. Чем ещё помочь?"
        return "Стой, путник. Гильдии спорят из-за старой башни. Соблюдай порядок."
    if settings.provider == "openai":
        from openai import OpenAI

        with OpenAI(timeout=settings.timeout, max_retries=0) as client:
            response = client.chat.completions.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
            )
        return response.choices[0].message.content or ""
    from anthropic import Anthropic

    with Anthropic(timeout=settings.timeout, max_retries=0) as client:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
    return "".join(block.text for block in response.content if block.type == "text")


def is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    return (
        isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError))
        or (type(exc).__name__ in {"APITimeoutError", "APIConnectionError"})
        or status in {408, 409, 429}
        or (status is not None and status >= 500)
    )


def call_with_fallback(settings, model: str, npc: str, message: str) -> Result:
    attempts = 0
    for candidate in dict.fromkeys([model, settings.fallback_model]):
        for retry in range(settings.attempts):
            attempts += 1
            try:
                reply = call(settings, candidate, npc, message)
                return Result(reply, candidate, attempts, candidate != model)
            except Exception as exc:
                if not is_transient(exc) or retry + 1 == settings.attempts:
                    break
                time.sleep(settings.retry_delay * 2**retry)
    # Bad credentials affect every model of one provider: use a static safe reply.
    return Result("NPC задумался. Пожалуйста, вернись чуть позже.", "fallback-static", attempts, True)
