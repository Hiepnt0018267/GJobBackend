"""Offline contract tests for the Ollama embedding adapter."""

import asyncio
import json
import math
from collections.abc import Callable

import httpx
import pytest

from app.embeddings.exceptions import (
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingInputTooLongError,
    EmbeddingProviderResponseError,
    EmbeddingProviderUnavailableError,
    EmbeddingValidationError,
)
from app.embeddings.ollama_provider import OllamaEmbeddingProvider


Handler = Callable[[httpx.Request], httpx.Response]


def _provider(handler: Handler) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url="http://ollama.test:11434/",
        model="bge-m3",
        timeout_seconds=3.5,
        transport=httpx.MockTransport(handler),
    )


def _embed(provider: OllamaEmbeddingProvider, texts: list[str]):
    return asyncio.run(provider.embed_many(texts))


def test_valid_batch_request_preserves_order_and_normalizes_metadata() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"model": "bge-m3:latest", "embeddings": [[1, 0], [0.25, 0.75]]},
        )

    result = _embed(_provider(handler), ["canonical cv", "canonical job"])

    assert captured == {
        "url": "http://ollama.test:11434/api/embed",
        "payload": {
            "model": "bge-m3",
            "input": ["canonical cv", "canonical job"],
            "truncate": False,
            "options": {"num_ctx":8192,"num_batch":4096},
        },
    }
    assert result.vectors == ((1.0, 0.0), (0.25, 0.75))
    assert result.provider == "ollama"
    assert result.model == "bge-m3:latest"
    assert result.dimensions == 2


@pytest.mark.parametrize("texts", [[], [""], ["   "], ["valid", "\t"]])
def test_empty_input_fails_before_http(texts: list[str]) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={})

    with pytest.raises(EmbeddingInputError):
        _embed(_provider(handler), texts)
    assert requests == 0


@pytest.mark.parametrize("vector_count", [0, 1, 3])
def test_response_requires_one_vector_per_input(vector_count: int) -> None:
    vectors = [[1.0, 2.0] for _ in range(vector_count)]

    with pytest.raises(EmbeddingValidationError, match="count"):
        _embed(
            _provider(
                lambda request: httpx.Response(
                    200, json={"model": "bge-m3", "embeddings": vectors}
                )
            ),
            ["cv", "job"],
        )


@pytest.mark.parametrize(
    ("payload", "error_type"),
    [
        ({}, EmbeddingValidationError),
        ({"model": "bge-m3"}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": "bad"}, EmbeddingValidationError),
        ({"model": "", "embeddings": [[1], [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [[], [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [None, [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [[1, 2], [1]]}, EmbeddingDimensionMismatchError),
        ({"model": "bge-m3", "embeddings": [[True], [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [["1"], [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [[math.nan], [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [[math.inf], [1]]}, EmbeddingValidationError),
        ({"model": "bge-m3", "embeddings": [[-math.inf], [1]]}, EmbeddingValidationError),
    ],
)
def test_malformed_vectors_fail_closed(
    payload: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        _embed(
            _provider(
                lambda request: httpx.Response(
                    200,
                    content=json.dumps(payload).encode(),
                    headers={"content-type": "application/json"},
                )
            ),
            ["cv", "job"],
        )


def test_unreadable_json_is_a_controlled_response_error() -> None:
    with pytest.raises(EmbeddingProviderResponseError, match="JSON"):
        _embed(
            _provider(lambda request: httpx.Response(200, content=b"not-json")),
            ["cv", "job"],
        )


@pytest.mark.parametrize(
    "exception_factory",
    [
        lambda request: httpx.ConnectError("offline", request=request),
        lambda request: httpx.ReadTimeout("slow", request=request),
    ],
)
def test_network_failure_is_controlled(
    exception_factory: Callable[[httpx.Request], Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception_factory(request)

    with pytest.raises(EmbeddingProviderUnavailableError):
        _embed(_provider(handler), ["cv", "job"])


def test_model_not_found_is_provider_unavailable_without_leaking_body() -> None:
    with pytest.raises(EmbeddingProviderUnavailableError, match="model") as exc_info:
        _embed(
            _provider(
                lambda request: httpx.Response(
                    404,
                    json={"error": "secret local filesystem model path"},
                )
            ),
            ["cv", "job"],
        )
    assert "filesystem" not in str(exc_info.value)


def test_context_overflow_is_distinct_and_never_retried() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            400,
            json={"error": "input length exceeds context length"},
        )

    with pytest.raises(EmbeddingInputTooLongError):
        _embed(_provider(handler), ["cv", "job"])
    assert requests == 1


def test_other_http_error_is_safe_and_not_retried() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500, text="sensitive upstream details")

    with pytest.raises(EmbeddingProviderResponseError, match="HTTP 500") as exc_info:
        _embed(_provider(handler), ["cv", "job"])
    assert "sensitive" not in str(exc_info.value)
    assert requests == 1
