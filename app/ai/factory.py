from app.ai.base import AIProvider
from app.ai.gemini_provider import GeminiProvider
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

    raise AIConfigurationError(f"Unsupported AI provider configured: '{provider_name}'")