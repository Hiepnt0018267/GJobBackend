import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIContextLimitError,
    AIProviderError,
    AIProviderRequestError,
    AIResponseValidationError,
    AITimeoutError,
)
from app.ai.factory import configured_ai_model, create_ai_provider
from app.ai.ollama_provider import OllamaProvider


class ExampleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    skills: list[str]


def _response(content: object, **metadata: object) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "qwen3:8b",
            "done": True,
            "message": {"role": "assistant", "content": content},
            **metadata,
        },
    )


def _provider(handler, **kwargs) -> OllamaProvider:
    return OllamaProvider(
        base_url="http://ollama.test:11434",
        model="qwen3:8b",
        timeout_seconds=2,
        num_ctx=8192,
        retry_delay_seconds=0,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_structured_generation_uses_raw_schema_and_validates_result() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _response(
            json.dumps({"name": "An", "skills": ["Python"]}),
            prompt_eval_count=800,
            eval_count=20,
            total_duration=2_000_000,
            load_duration=500_000,
        )

    provider = _provider(handler)
    result = asyncio.run(
        provider.generate_structured(
            "CV text",
            ExampleResult,
            system_instruction="Extract facts only",
        )
    )

    assert result == ExampleResult(name="An", skills=["Python"])
    assert captured["model"] == "qwen3:8b"
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["format"] == ExampleResult.model_json_schema()
    assert captured["options"] == {"temperature": 0.0, "num_ctx": 8192}
    messages = captured["messages"]
    assert messages[0] == {"role": "system", "content": "Extract facts only"}
    assert messages[1]["role"] == "user"
    assert messages[1]["content"].startswith("CV text\n\nReturn data matching")
    assert '"properties"' in messages[1]["content"]
    assert provider.last_metrics is not None
    assert provider.last_metrics.prompt_eval_count == 800
    assert provider.last_metrics.eval_count == 20
    assert provider.last_metrics.context_ratio == pytest.approx(800 / 8192)


def test_generate_text_accepts_missing_optional_metrics() -> None:
    provider = _provider(lambda _: _response("  ready  "))

    assert asyncio.run(provider.generate_text("ping")) == "ready"
    assert provider.last_metrics is not None
    assert provider.last_metrics.prompt_eval_count is None
    assert provider.last_metrics.context_ratio is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"done": False, "message": {"content": "{}"}}),
        httpx.Response(200, json={"done": True}),
        _response(""),
    ],
)
def test_invalid_envelope_fails_without_retry(response: httpx.Response) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    with pytest.raises(AIResponseValidationError):
        asyncio.run(_provider(handler).generate_text("ping"))
    assert calls == 1


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        json.dumps({"name": "An"}),
        json.dumps({"name": "An", "skills": [], "extra": True}),
    ],
)
def test_invalid_structured_content_fails_without_repair(content: str) -> None:
    provider = _provider(lambda _: _response(content))

    with pytest.raises(AIResponseValidationError):
        asyncio.run(provider.generate_structured("CV", ExampleResult))


def test_actual_context_saturation_fails_closed() -> None:
    provider = OllamaProvider(
        base_url="http://ollama.test:11434",
        model="qwen3:8b",
        timeout_seconds=2,
        num_ctx=1000,
        retry_delay_seconds=0,
        transport=httpx.MockTransport(
            lambda _: _response(
                json.dumps({"name": "An", "skills": []}),
                prompt_eval_count=950,
            )
        ),
    )

    with pytest.raises(AIContextLimitError):
        asyncio.run(provider.generate_structured("CV", ExampleResult))
    assert provider.last_metrics is not None
    assert provider.last_metrics.context_ratio == 0.95


def test_4xx_is_not_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "bad request"})

    with pytest.raises(AIProviderRequestError, match="HTTP 400"):
        asyncio.run(_provider(handler).generate_text("ping"))
    assert calls == 1


def test_5xx_is_retried_once() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "busy"})
        return _response("ready")

    assert asyncio.run(_provider(handler).generate_text("ping")) == "ready"
    assert calls == 2


def test_exhausted_5xx_is_provider_unavailable_not_request_invalid() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": "busy"})

    with pytest.raises(AIProviderError, match="HTTP 503") as raised:
        asyncio.run(_provider(handler).generate_text("ping"))
    assert not isinstance(raised.value, AIProviderRequestError)
    assert calls == 2


def test_connect_failure_is_retried_once_then_fails() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(AIProviderError, match="unavailable"):
        asyncio.run(_provider(handler).generate_text("ping"))
    assert calls == 2


def test_timeout_is_retried_once_then_normalized() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AITimeoutError, match="timeout"):
        asyncio.run(_provider(handler).generate_text("ping"))
    assert calls == 2


def test_factory_selects_ollama_with_independent_llm_settings(monkeypatch) -> None:
    monkeypatch.setattr("app.ai.factory.settings.ai_provider", " OLLAMA ")
    monkeypatch.setattr("app.ai.factory.settings.ollama_base_url", "http://local")
    monkeypatch.setattr("app.ai.factory.settings.ollama_llm_model", "qwen3:test")
    monkeypatch.setattr("app.ai.factory.settings.ollama_llm_timeout_seconds", 44)
    monkeypatch.setattr("app.ai.factory.settings.ollama_llm_num_ctx", 4096)

    provider = create_ai_provider()

    assert isinstance(provider, OllamaProvider)
    assert isinstance(provider, AIProvider)
    assert provider._base_url == "http://local"
    assert provider._model == "qwen3:test"
    assert provider._timeout_seconds == 44
    assert provider._num_ctx == 4096
    assert configured_ai_model() == "qwen3:test"
