"""SDK adapter tests with local HTTP transport; no external API requests."""

import httpx
import openai
import pytest

from gateway import llm


@pytest.mark.parametrize("status,expected_attempts", [(200, 1), (401, 2), (429, 6), (500, 6)])
def test_openai_adapter(settings, monkeypatch, status, expected_attempts):
    actual = openai.OpenAI
    requests = []

    def handle(request):
        requests.append(request)
        if status == 200:
            return httpx.Response(
                200,
                json={
                    "id": "local",
                    "object": "chat.completion",
                    "created": 0,
                    "model": settings.strong_model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Local SDK answer."},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )
        return httpx.Response(status, json={"error": {"message": "injected", "type": "api_error"}})

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0 and kwargs["timeout"] == settings.timeout
        return actual(
            api_key="local-test-only",
            base_url="https://mock.test/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            **kwargs,
        )

    monkeypatch.setattr(openai, "OpenAI", factory)
    settings.provider = "openai"
    result = llm.call_with_fallback(settings, settings.strong_model, "trader", "Привет")
    assert result.attempts == expected_attempts == len(requests)
    assert result.model == (settings.strong_model if status == 200 else "fallback-static")
    if status == 200:
        assert result.reply == "Local SDK answer."
