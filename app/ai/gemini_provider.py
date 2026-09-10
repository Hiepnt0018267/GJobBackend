import logging
import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIProviderError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
)

logger = logging.getLogger("gjob.ai.gemini")

# Custom transient exception để quản lý retry nội bộ
class _TransientAIError(Exception):
    pass

class GeminiProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        # Tuyệt đối không log self.api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout * 1000)))

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction if system_instruction else None,
        )

        @retry(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type(_TransientAIError),
            reraise=True,
        )
        async def _execute():
            try:
                # Client async chính thức từ google-genai
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                return response
            except APIError as exc:
                # Mapping mã lỗi upstream từ Google GenAI
                status_code = getattr(exc, "code", None)
                if status_code in (401, 403):
                    logger.error("Gemini auth error (status=%s)", status_code)
                    raise AIAuthenticationError("Invalid or unauthorized Gemini API key") from exc
                elif status_code == 429:
                    logger.warning("Gemini rate limit encountered. Attempting retry...")
                    raise _TransientAIError("Gemini rate limited") from exc
                elif status_code and status_code >= 500:
                    logger.warning("Gemini server error (status=%s). Attempting retry...", status_code)
                    raise _TransientAIError("Gemini internal server error") from exc
                else:
                    logger.error("Gemini API error (status=%s)", status_code)
                    raise AIProviderError(f"Gemini API returned error: {status_code}") from exc
            except (TimeoutError, httpx.TimeoutException) as exc:
                logger.warning("Gemini timeout encountered. Attempting retry...")
                raise _TransientAIError("Gemini call timed out") from exc
            except Exception as exc:
                logger.error("Unexpected error contacting Gemini: %s", type(exc).__name__)
                raise AIProviderError("Unexpected Gemini provider failure") from exc

        try:
            raw_response = await _execute()
        except _TransientAIError as exc:
            # Nếu retry hết lượt mà vẫn dính lỗi transient
            if "timed out" in str(exc):
                raise AITimeoutError("Gemini request timed out after retries") from exc
            if "rate limited" in str(exc):
                raise AIRateLimitError("Gemini quota / rate limit exceeded") from exc
            raise AIProviderError("Gemini request failed after maximum retries") from exc

        # Chuẩn hóa kết quả trả về
        if not raw_response or not raw_response.text:
            logger.error("Gemini returned an empty or unparseable response")
            raise AIProviderError("Gemini returned empty text response")

        return raw_response.text.strip()
