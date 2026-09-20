import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from google.genai.errors import APIError
from tenacity import wait_none

from app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIProviderError,
    AIProviderRequestError,
    AIRateLimitError,
    AIResponseValidationError,
    AITimeoutError,
)
from app.ai.factory import create_ai_provider
from app.ai.gemini_provider import GeminiProvider
from app.ai.gemini_retry import (
    GeminiRetryWait,
    TransientRateLimitError,
    retry_after_seconds,
)
from app.schemas.cv_extraction import StructuredCVExtractionResult


@pytest.fixture
def provider():
    with patch("app.ai.gemini_provider.genai.Client"):
        return GeminiProvider(
            api_key="fake-test-key",
            model="gemini-3.8-flash",
            max_retries=1,
            retry_wait=wait_none(),
        )


def test_factory_missing_key(monkeypatch):
    monkeypatch.setattr("app.ai.factory.settings.ai_provider", "gemini")
    monkeypatch.setattr("app.ai.factory.settings.gemini_api_key", "")
    with pytest.raises(AIConfigurationError, match="GEMINI_API_KEY is missing"):
        create_ai_provider()


def test_factory_unsupported_provider(monkeypatch):
    monkeypatch.setattr("app.ai.factory.settings.ai_provider", "unsupported_llm")
    with pytest.raises(AIConfigurationError, match="Unsupported AI provider"):
        create_ai_provider()


def test_generate_text_success(provider):
    mock_response = MagicMock()
    mock_response.text = "GJOB_GEMINI_OK\n"
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    res = asyncio.run(provider.generate_text("Reply with exactly: GJOB_GEMINI_OK"))
    assert res == "GJOB_GEMINI_OK"


def test_generate_text_empty_response(provider):
    mock_response = MagicMock()
    mock_response.text = ""
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with pytest.raises(AIProviderError, match="empty text response"):
        asyncio.run(provider.generate_text("Hello"))


def test_generate_text_auth_error_no_retry(provider):
    err = APIError(401, {"error": {"message": "Unauthorized"}})
    provider.client.aio.models.generate_content = AsyncMock(side_effect=err)

    with pytest.raises(AIAuthenticationError):
        asyncio.run(provider.generate_text("Hello"))

    # Xác nhận chỉ gọi 1 lần, không retry
    assert provider.client.aio.models.generate_content.call_count == 1


def test_generate_text_rate_limit_retries_and_fails(provider):
    err = APIError(429, {"error": {"message": "Rate limited"}})
    provider.client.aio.models.generate_content = AsyncMock(side_effect=err)

    with pytest.raises(AIRateLimitError):
        asyncio.run(provider.generate_text("Hello"))

    # max_retries = 1 => 1 lần gọi đầu + 1 lần retry = 2 lần
    assert provider.client.aio.models.generate_content.call_count == 2


def test_rate_limit_once_then_success(provider):
    response = MagicMock()
    response.text = "recovered"
    provider.client.aio.models.generate_content = AsyncMock(
        side_effect=[
            APIError(429, {"error": {"message": "Rate limited"}}),
            response,
        ]
    )

    assert asyncio.run(provider.generate_text("synthetic")) == "recovered"
    assert provider.client.aio.models.generate_content.call_count == 2


def test_two_rate_limits_then_success_with_bounded_attempts():
    with patch("app.ai.gemini_provider.genai.Client"):
        provider = GeminiProvider(
            api_key="fake-test-key",
            model="gemini-3.8-flash",
            max_retries=2,
            retry_wait=wait_none(),
        )
    response = MagicMock()
    response.text = "recovered"
    rate_limit = APIError(429, {"error": {"message": "Rate limited"}})
    provider.client.aio.models.generate_content = AsyncMock(
        side_effect=[rate_limit, rate_limit, response]
    )

    assert asyncio.run(provider.generate_text("synthetic")) == "recovered"
    assert provider.client.aio.models.generate_content.call_count == 3


def test_retry_after_prefers_header_then_structured_metadata():
    response = httpx.Response(429, headers={"Retry-After": "5"})
    from_header = APIError(429, {"error": {"message": "limited"}}, response)
    from_metadata = APIError(
        429,
        {
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "3.5s",
                    }
                ]
            }
        },
    )

    assert retry_after_seconds(from_header) == 5.0
    assert retry_after_seconds(from_metadata) == 3.5


def test_retry_wait_uses_exponential_jitter_fallback_and_bounds_retry_after():
    no_jitter = GeminiRetryWait(random_source=lambda _low, _high: 0.0)
    max_jitter = GeminiRetryWait(random_source=lambda _low, high: high)

    assert no_jitter.delay_for(1, TransientRateLimitError(None)) == 1.0
    assert no_jitter.delay_for(2, TransientRateLimitError(None)) == 2.0
    assert no_jitter.delay_for(1, TransientRateLimitError(0.0)) == 1.0
    assert no_jitter.delay_for(1, TransientRateLimitError(600.0)) == 8.0
    assert max_jitter.delay_for(1, TransientRateLimitError(None)) == 2.0


def test_invalid_request_is_classified_and_not_retried(provider):
    err = APIError(
        400,
        {"error": {"message": "Unknown name additional_properties"}},
    )
    provider.client.aio.models.generate_content = AsyncMock(side_effect=err)

    with pytest.raises(AIProviderRequestError):
        asyncio.run(provider.generate_text("synthetic"))

    assert provider.client.aio.models.generate_content.call_count == 1


@pytest.mark.parametrize(
    ("error", "expected_exception"),
    [
        (httpx.ReadTimeout("timed out"), AITimeoutError),
        (httpx.ConnectError("offline"), AIProviderError),
        (APIError(500, {"error": {"message": "server error"}}), AIProviderError),
    ],
)
def test_transient_errors_keep_retry_policy(provider, error, expected_exception):
    provider.client.aio.models.generate_content = AsyncMock(side_effect=error)

    with pytest.raises(expected_exception):
        asyncio.run(provider.generate_text("synthetic"))

    assert provider.client.aio.models.generate_content.call_count == 2


def test_generate_structured_uses_native_schema_and_configured_model(provider):
    payload = {"personal_info": {"full_name": "Nguyễn Văn A"}}
    mock_response = MagicMock()
    mock_response.parsed = payload
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    result = asyncio.run(
        provider.generate_structured(
            "untrusted CV data",
            StructuredCVExtractionResult,
            system_instruction="extract only",
            temperature=0.0,
        )
    )

    assert result == payload
    call = provider.client.aio.models.generate_content.await_args
    assert call.kwargs["model"] == "gemini-3.8-flash"
    config = call.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert isinstance(config.response_schema, dict)
    assert config.response_json_schema is None
    assert "additionalProperties" not in str(config.response_schema)
    assert "maxItems" not in str(config.response_schema)
    assert "maxLength" in str(config.response_schema)
    assert "personal_info" in config.response_schema["properties"]
    assert config.temperature == 0.0
    assert config.system_instruction == "extract only"


def test_generate_structured_rejects_malformed_fallback_json(provider):
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = "not-json"
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with pytest.raises(AIResponseValidationError, match="malformed"):
        asyncio.run(
            provider.generate_structured(
                "untrusted CV data", StructuredCVExtractionResult
            )
        )
