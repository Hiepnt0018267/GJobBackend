import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai.errors import APIError

from app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseValidationError,
)
from app.ai.factory import create_ai_provider
from app.ai.gemini_provider import GeminiProvider
from app.schemas.cv_extraction import StructuredCVExtractionResult


@pytest.fixture
def provider():
    with patch("app.ai.gemini_provider.genai.Client"):
        return GeminiProvider(
            api_key="fake-test-key", model="gemini-3.8-flash", max_retries=1
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
    assert config.response_schema is StructuredCVExtractionResult
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
