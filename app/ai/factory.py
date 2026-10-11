from app.ai.base import AIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.exceptions import AIConfigurationError
from app.core.config import settings

def create_ai_provider() -> AIProvider:
    provider_name = (settings.ai_provider or "").lower().strip()

    if provider_name == "gemini":
        if not settings.gemini_api_key or not settings.gemini_api_key.strip():
            raise AIConfigurationError("GEMINI_API_KEY is missing or empty in configuration")

        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_llm_model,
            timeout_seconds=settings.ollama_llm_timeout_seconds,
            num_ctx=settings.ollama_llm_num_ctx,
            num_predict=settings.ollama_llm_num_predict,
            safety_margin=settings.ollama_llm_safety_margin,
        )

    raise AIConfigurationError(f"Unsupported AI provider configured: '{provider_name}'")


def configured_ai_model() -> str:
    """Return the configured model for persistence without creating a client."""
    provider_name = (settings.ai_provider or "").lower().strip()
    if provider_name == "gemini":
        return settings.gemini_model
    if provider_name == "ollama":
        return settings.ollama_llm_model
    raise AIConfigurationError(f"Unsupported AI provider configured: '{provider_name}'")

