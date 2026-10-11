"""Embedding settings remain independent from generation settings."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


BASE_SETTINGS = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@localhost/example",
    "SECRET_KEY": "test-secret",
}


def test_embedding_settings_defaults() -> None:
    configured = Settings(_env_file=None, **BASE_SETTINGS)

    assert configured.embedding_provider == "ollama"
    assert configured.embedding_model == "bge-m3"
    assert configured.ollama_base_url == "http://localhost:11434"
    assert configured.embedding_timeout_seconds == 30.0
    assert configured.embedding_num_ctx==8192
    assert configured.embedding_num_batch==4096
    assert configured.ollama_llm_model == "qwen3:8b"
    assert configured.ollama_llm_timeout_seconds == 165.0
    assert configured.ollama_llm_num_ctx == 10240


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("embedding_provider", ""),
        ("embedding_model", "   "),
        ("ollama_base_url", "\t"),
        ("embedding_timeout_seconds", 0),
        ("embedding_timeout_seconds", -1),
        ("embedding_timeout_seconds", 121),
        ("embedding_num_ctx", 1023),
        ("embedding_num_ctx", 8193),
        ("embedding_num_batch", 1023),
        ("embedding_num_batch", 4097),
        ("ollama_llm_model", ""),
        ("ollama_llm_timeout_seconds", 0),
        ("ollama_llm_timeout_seconds", 181),
        ("ollama_llm_num_ctx", 1023),
        ("ollama_llm_num_ctx", 131_073),
    ],
)
def test_invalid_embedding_settings_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **BASE_SETTINGS, **{field: value})


def test_embedding_settings_do_not_reuse_gemini_retry_configuration() -> None:
    configured = Settings(
        _env_file=None,
        **BASE_SETTINGS,
        ai_max_retries=5,
        embedding_timeout_seconds=12,
    )

    assert configured.ai_max_retries == 5
    assert configured.embedding_timeout_seconds == 12
    assert "embedding_max_retries" not in Settings.model_fields
