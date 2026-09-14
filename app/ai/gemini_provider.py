import json
import logging

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIAuthenticationError,
    AIProviderError,
    AIRateLimitError,
    AIResponseValidationError,
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
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )

    async def _generate_content(
        self,
        prompt: str,
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        @retry(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type(_TransientAIError),
            reraise=True,
        )
        async def _execute() -> types.GenerateContentResponse:
            try:
                return await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
            except APIError as exc:
                status_code = getattr(exc, "code", None)
                if status_code in (401, 403):
                    logger.error("Gemini auth error (status=%s)", status_code)
                    raise AIAuthenticationError(
                        "Invalid or unauthorized Gemini API key"
                    ) from exc
                if status_code == 429:
                    logger.warning("Gemini rate limit encountered. Attempting retry...")
                    raise _TransientAIError("Gemini rate limited") from exc
                if status_code and status_code >= 500:
                    logger.warning(
                        "Gemini server error (status=%s). Attempting retry...",
                        status_code,
                    )
                    raise _TransientAIError("Gemini internal server error") from exc
                logger.error("Gemini API error (status=%s)", status_code)
                raise AIProviderError(f"Gemini API returned error: {status_code}") from exc
            except (TimeoutError, httpx.TimeoutException) as exc:
                logger.warning("Gemini timeout encountered. Attempting retry...")
                raise _TransientAIError("Gemini call timed out") from exc
            except Exception as exc:
                logger.error("Unexpected error contacting Gemini: %s", type(exc).__name__)
                raise AIProviderError("Unexpected Gemini provider failure") from exc

        try:
            return await _execute()
        except _TransientAIError as exc:
            if "timed out" in str(exc):
                raise AITimeoutError("Gemini request timed out after retries") from exc
            if "rate limited" in str(exc):
                raise AIRateLimitError("Gemini quota / rate limit exceeded") from exc
            raise AIProviderError("Gemini request failed after maximum retries") from exc

    @staticmethod
    def _response_text(raw_response: types.GenerateContentResponse) -> str:
        try:
            response_text = raw_response.text
        except Exception as exc:
            logger.error("Gemini returned an unusable response")
            raise AIResponseValidationError("Gemini returned an unusable response") from exc
        if not response_text or not response_text.strip():
            logger.error("Gemini returned an empty or unparseable response")
            raise AIResponseValidationError("Gemini returned empty text response")
        return response_text.strip()

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

        raw_response = await self._generate_content(prompt, config)
        return self._response_text(raw_response)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> object:
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction if system_instruction else None,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        raw_response = await self._generate_content(prompt, config)
        parsed = getattr(raw_response, "parsed", None)
        if parsed is not None:
            return parsed

        response_text = self._response_text(raw_response)
        try:
            return json.loads(response_text)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Gemini returned malformed structured output")
            raise AIResponseValidationError(
                "Gemini returned malformed structured output"
            ) from exc
