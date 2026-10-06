"""Local Ollama implementation of the shared AI generation contract."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIContextLimitError,
    AIProviderError,
    AIProviderRequestError,
    AIResponseValidationError,
    AITimeoutError,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OllamaGenerationMetrics:
    model: str
    prompt_eval_count: int | None
    eval_count: int | None
    total_duration_ns: int | None
    load_duration_ns: int | None
    context_ratio: float | None
    elapsed_seconds: float


class OllamaProvider(AIProvider):
    """Generate text or schema-constrained JSON through Ollama's chat API."""

    provider_name = "ollama"
    _CONTEXT_SATURATION_RATIO = 0.95

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 90.0,
        num_ctx: int = 8192,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.25,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._num_ctx = num_ctx
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._transport = transport
        self.last_metrics: OllamaGenerationMetrics | None = None

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        payload = self._base_payload(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
        )
        response_payload = await self._request(payload)
        return self._response_content(response_payload)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_instruction: str | None = None,
        temperature: float = 0.0,
    ) -> object:
        schema = response_schema.model_json_schema()
        payload = self._base_payload(
            prompt=(
                f"{prompt}\n\nReturn data matching this exact JSON schema:\n"
                f"{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}"
            ),
            system_instruction=system_instruction,
            temperature=temperature,
        )
        payload["format"] = schema
        response_payload = await self._request(payload)
        content = self._response_content(response_payload)

        try:
            decoded = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise AIResponseValidationError(
                "Ollama returned malformed structured JSON."
            ) from exc

        try:
            return response_schema.model_validate(decoded)
        except ValidationError as exc:
            raise AIResponseValidationError(
                "Ollama returned data that does not match the requested schema."
            ) from exc

    def _base_payload(
        self,
        *,
        prompt: str,
        system_instruction: str | None,
        temperature: float,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_ctx": self._num_ctx,
            },
        }

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = time.perf_counter()
        timeout = httpx.Timeout(
            self._timeout_seconds,
            connect=min(5.0, self._timeout_seconds),
        )
        try:
            async with asyncio.timeout(self._timeout_seconds):
                for attempt in range(self._max_retries + 1):
                    try:
                        async with httpx.AsyncClient(
                            base_url=self._base_url,
                            timeout=timeout,
                            transport=self._transport,
                        ) as client:
                            response = await client.post("/api/chat", json=payload)
                    except (httpx.ConnectError, httpx.TimeoutException) as exc:
                        if attempt < self._max_retries:
                            await asyncio.sleep(self._retry_delay_seconds)
                            continue
                        if isinstance(exc, httpx.TimeoutException):
                            raise AITimeoutError(
                                "Ollama did not respond before the timeout."
                            ) from exc
                        raise AIProviderError("Ollama is unavailable.") from exc
                    except httpx.RequestError as exc:
                        raise AIProviderError("Ollama is unavailable.") from exc

                    if response.status_code >= 500 and attempt < self._max_retries:
                        await asyncio.sleep(self._retry_delay_seconds)
                        continue
                    if response.status_code >= 500:
                        raise AIProviderError(
                            f"Ollama returned HTTP {response.status_code}."
                        )
                    if not response.is_success:
                        raise AIProviderRequestError(
                            f"Ollama rejected the request with HTTP {response.status_code}."
                        )
                    return self._parse_response(
                        response,
                        elapsed_seconds=time.perf_counter() - started_at,
                    )
        except TimeoutError as exc:
            raise AITimeoutError("Ollama did not respond before the timeout.") from exc

        raise AIProviderError("Ollama request did not complete.")

    def _parse_response(
        self,
        response: httpx.Response,
        *,
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIResponseValidationError(
                "Ollama returned an unreadable response."
            ) from exc
        if not isinstance(payload, dict):
            raise AIResponseValidationError("Ollama response must be an object.")
        if payload.get("done") is not True:
            raise AIResponseValidationError("Ollama returned an incomplete response.")

        prompt_eval_count = self._optional_non_negative_int(
            payload, "prompt_eval_count"
        )
        eval_count = self._optional_non_negative_int(payload, "eval_count")
        total_duration_ns = self._optional_non_negative_int(payload, "total_duration")
        load_duration_ns = self._optional_non_negative_int(payload, "load_duration")
        context_ratio = (
            prompt_eval_count / self._num_ctx
            if prompt_eval_count is not None
            else None
        )
        self.last_metrics = OllamaGenerationMetrics(
            model=self._model,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
            total_duration_ns=total_duration_ns,
            load_duration_ns=load_duration_ns,
            context_ratio=context_ratio,
            elapsed_seconds=elapsed_seconds,
        )
        logger.info(
            "Ollama generation completed model=%s prompt_tokens=%s output_tokens=%s "
            "context_ratio=%s elapsed_seconds=%.3f",
            self._model,
            prompt_eval_count,
            eval_count,
            f"{context_ratio:.3f}" if context_ratio is not None else "unknown",
            elapsed_seconds,
        )
        if (
            context_ratio is not None
            and context_ratio >= self._CONTEXT_SATURATION_RATIO
        ):
            raise AIContextLimitError(
                "Ollama prompt consumed the configured context safety limit."
            )
        return payload

    @staticmethod
    def _response_content(payload: dict[str, Any]) -> str:
        message = payload.get("message")
        if not isinstance(message, dict):
            raise AIResponseValidationError("Ollama response is missing its message.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIResponseValidationError("Ollama returned empty content.")
        return content.strip()

    @staticmethod
    def _optional_non_negative_int(
        payload: dict[str, Any], field: str
    ) -> int | None:
        value = payload.get(field)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AIResponseValidationError(
                f"Ollama response has invalid {field} metadata."
            )
        return value
