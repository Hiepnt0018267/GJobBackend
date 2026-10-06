import json
import logging
from typing import cast

import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt
from tenacity.wait import wait_base

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIAuthenticationError,
    AIProviderError,
    AIProviderRequestError,
    AIRateLimitError,
    AIResponseValidationError,
    AITimeoutError,
)
from app.ai.gemini_schema import JSONValue, sanitize_schema_for_gemini
from app.ai.gemini_retry import (
    GeminiRetryWait,
    TransientAIError,
    TransientProviderError,
    TransientRateLimitError,
    TransientTimeoutError,
    retry_after_seconds,
)

logger = logging.getLogger("gjob.ai.gemini")

class GeminiProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_wait: wait_base | None = None,
    ):
        # Tuyệt đối không log self.api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_wait = retry_wait if retry_wait is not None else GeminiRetryWait()
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
            wait=self.retry_wait,
            retry=retry_if_exception_type(TransientAIError),
            before_sleep=self._log_before_sleep,
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
                    raise TransientRateLimitError(retry_after_seconds(exc)) from exc
                if status_code and 400 <= status_code < 500:
                    logger.error(
                        "Gemini request rejected (status=%s, error_type=%s)",
                        status_code,
                        type(exc).__name__,
                    )
                    raise AIProviderRequestError(
                        "Gemini rejected the request configuration"
                    ) from exc
                if status_code and status_code >= 500:
                    raise TransientProviderError(
                        "Gemini internal server error"
                    ) from exc
                logger.error(
                    "Gemini API error (status=%s, error_type=%s)",
                    status_code,
                    type(exc).__name__,
                )
                raise AIProviderError(f"Gemini API returned error: {status_code}") from exc
            except (TimeoutError, httpx.TimeoutException) as exc:
                raise TransientTimeoutError("Gemini call timed out") from exc
            except httpx.NetworkError as exc:
                raise TransientProviderError("Gemini network failure") from exc
            except Exception as exc:
                logger.error("Unexpected error contacting Gemini: %s", type(exc).__name__)
                raise AIProviderError("Unexpected Gemini provider failure") from exc

        try:
            return await _execute()
        except TransientAIError as exc:
            logger.warning(
                "Gemini retries exhausted (attempts=%s, reason=%s)",
                self.max_retries + 1,
                exc.kind,
            )
            if isinstance(exc, TransientTimeoutError):
                raise AITimeoutError("Gemini request timed out after retries") from exc
            if isinstance(exc, TransientRateLimitError):
                raise AIRateLimitError("Gemini quota / rate limit exceeded") from exc
            raise AIProviderError("Gemini request failed after maximum retries") from exc

    def _log_before_sleep(self, retry_state: RetryCallState) -> None:
        error = (
            retry_state.outcome.exception()
            if retry_state.outcome is not None
            else None
        )
        wait_seconds = (
            retry_state.next_action.sleep
            if retry_state.next_action is not None
            else 0.0
        )
        logger.warning(
            "Gemini transient failure; retry scheduled "
            "(next_attempt=%s/%s, wait_seconds=%.2f, reason=%s)",
            retry_state.attempt_number + 1,
            self.max_retries + 1,
            wait_seconds,
            error.kind if isinstance(error, TransientAIError) else "provider",
        )

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

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Strip optional markdown code fences (```json ... ```) from a response."""
        stripped = text.strip()
        # Remove opening fence: ```json or ```
        if stripped.startswith("```"):
            first_newline = stripped.find("\n")
            if first_newline != -1:
                stripped = stripped[first_newline + 1:]
        # Remove closing fence
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
        return stripped.strip()

    async def _generate_structured_text_fallback(
        self,
        prompt: str,
        system_instruction: str | None,
        temperature: float,
    ) -> object:
        """Fallback: ask model to output JSON as plain text, then parse manually."""
        json_instruction = (
            "\n\nIMPORTANT: Respond with ONLY a valid JSON object. "
            "Do not include any explanation, markdown, or code fences."
        )
        text_config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction if system_instruction else None,
        )
        logger.warning(
            "Gemini structured output unavailable; retrying with text-mode fallback"
        )
        raw_response = await self._generate_content(prompt + json_instruction, text_config)
        response_text = self._response_text(raw_response)
        clean_text = self._extract_json_block(response_text)
        try:
            return json.loads(clean_text)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Gemini text-mode fallback returned malformed JSON")
            raise AIResponseValidationError(
                "Gemini text-mode fallback returned malformed JSON"
            ) from exc

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> object:
        domain_schema = cast(JSONValue, response_schema.model_json_schema())
        provider_schema = sanitize_schema_for_gemini(domain_schema)
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction if system_instruction else None,
            response_mime_type="application/json",
            response_schema=provider_schema,
        )
        try:
            raw_response = await self._generate_content(prompt, config)
        except (AIProviderError, AIRateLimitError, AITimeoutError) as exc:
            # Structured endpoint overloaded — attempt text-mode fallback
            logger.warning(
                "Gemini structured output failed (%s); attempting text-mode fallback",
                type(exc).__name__,
            )
            return await self._generate_structured_text_fallback(
                prompt, system_instruction, temperature
            )

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
