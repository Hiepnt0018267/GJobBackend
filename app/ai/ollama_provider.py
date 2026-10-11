"""Local Ollama implementation of the shared AI generation contract."""

import asyncio
import json
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.extraction_diagnostics import CURRENT, stage
from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIContextLimitError,
    AIProviderError,
    AIProviderRequestError,
    AIResponseValidationError,
    AITimeoutError,
    AIContextBudgetExceededError,
    AIOutputBudgetExceededError,
    AIJSONParseError,
    AISchemaValidationError,
    AITokenAccountingUnavailableError,
)
from app.ai.ollama_token_budget import OllamaRuntimeTokenCounter, PromptAccounting, EXTRACTION_BUDGET_PROFILE_VERSION


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
    done_reason: str | None = None
    prompt_eval_duration_ns: int | None = None
    eval_duration_ns: int | None = None
    done: bool | None = None


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
        num_ctx: int = 10240,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.25,
        transport: httpx.AsyncBaseTransport | None = None,
        structured_response_observer: Callable[[str, OllamaGenerationMetrics | None], None] | None = None,
        num_predict: int = 4608,
        safety_margin: int = 256,
        token_counter=None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._num_ctx = num_ctx
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._transport = transport
        self.last_metrics: OllamaGenerationMetrics | None = None
        self.structured_response_observer = structured_response_observer
        if num_predict <= 0 or safety_margin <= 0:
            raise ValueError("Extraction output and safety budgets must be positive.")
        self._num_predict = num_predict
        self._safety_margin = safety_margin
        self.token_counter = token_counter or OllamaRuntimeTokenCounter(self._base_url, timeout_seconds)
        self.last_accounting: PromptAccounting | None = None
        self.structured_profile = {"version": EXTRACTION_BUDGET_PROFILE_VERSION,
            "model": model, "num_ctx": num_ctx, "num_predict": num_predict,
            "safety_margin": safety_margin, "shift": False, "truncate": False,
            "think": False, "temperature": 0, "provider_timeout_seconds": timeout_seconds}
        self.structured_profile_fingerprint = hashlib.sha256(json.dumps(
            self.structured_profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

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
        with stage('correction_build_ms' if CURRENT.get() and CURRENT.get().attempt > 1 else 'prompt_build_ms'):
            schema = response_schema.model_json_schema()
            full_prompt = (
                f"{prompt}\n\nReturn data matching this exact JSON schema:\n"
                f"{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}"
            )
            # num_predict MUST be set before the token counter call so it is always
            # present in the payload even if the token counter raises.
            payload = self._base_payload(
                prompt=full_prompt,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            payload["format"] = schema
            payload["options"]["num_predict"] = self._num_predict
            payload["shift"] = False
            payload["truncate"] = False
        self.last_metrics = None
        self.last_accounting = None
        try:
            with stage('token_count_ms'):
                self.last_accounting = await self.token_counter.count(payload)
            with stage('preflight_ms'):
                self._check_preflight(self.last_accounting)
        except AITokenAccountingUnavailableError:
            # Diagnostic ONLY. An estimate must never accept/reject CV admission.
            rendered_len = sum(len(m.get("content", "")) for m in payload["messages"])
            approx_prompt_tokens = rendered_len // 3 + 512
            required_approx = approx_prompt_tokens + self._num_predict + self._safety_margin
            logger.warning(
                "Extraction preflight APPROXIMATE profile=%s approx_prompt_tokens=%s "
                "output_reserved=%s safety=%s effective_ctx=%s remaining=%s "
                "(authoritative token accounting unavailable)",
                EXTRACTION_BUDGET_PROFILE_VERSION,
                approx_prompt_tokens, self._num_predict, self._safety_margin,
                self._num_ctx, self._num_ctx - required_approx,
            )
            with stage('token_count_ms'):
                await self.token_counter.verify_safe_runtime()
            diagnostics = CURRENT.get()
            if diagnostics is not None:
                diagnostics.clear_handled_terminal('token_count_ms')
            logger.warning("Extraction uses bounded runtime admission; shift=false truncate=false; exact count unavailable")
        response_payload = await self._request(payload)
        content = self._response_content(response_payload)

        try:
            with stage(f'json_parse_{CURRENT.get().attempt if CURRENT.get() else 1}_ms'):
                decoded = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            failure_type = AIOutputBudgetExceededError if self.last_metrics and self.last_metrics.eval_count == self._num_predict else AIJSONParseError
            raise failure_type(
                "Ollama returned malformed structured JSON."
            ) from exc

        try:
            with stage(f'schema_validate_{CURRENT.get().attempt if CURRENT.get() else 1}_ms'):
                return response_schema.model_validate(decoded)
        except ValidationError as exc:
            failure = AISchemaValidationError(
                "Ollama returned data that does not match the requested schema."
            )
            # Ephemeral schema-repair input only, excluded from exception text,
            # logs, API responses and persistent extraction state.
            failure._invalid_payload = decoded
            raise failure from exc

    def _check_preflight(self, a):
        required = a.prompt_tokens + a.special_tokens + self._num_predict + self._safety_margin
        logger.info(
            "Extraction preflight profile=%s prompt_tokens=%s output_reserved=%s "
            "specials=%s safety=%s effective_ctx=%s remaining=%s",
            EXTRACTION_BUDGET_PROFILE_VERSION,
            a.prompt_tokens, self._num_predict, a.special_tokens, self._safety_margin,
            a.effective_num_ctx, a.effective_num_ctx - required,
        )
        if required > a.effective_num_ctx:
            raise AIContextBudgetExceededError(
                "CV prompt and reserved output exceed the extraction context budget."
            )

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
        diagnostics = CURRENT.get() if 'format' in payload else None
        effective_timeout = diagnostics.begin_call(self._timeout_seconds, self._num_predict) if diagnostics else self._timeout_seconds
        timeout = httpx.Timeout(effective_timeout, connect=min(5.0, effective_timeout))
        try:
            async with asyncio.timeout(effective_timeout):
                for attempt in range(self._max_retries + 1):
                    # The existing retry group is bounded too: each HTTP request
                    # receives only its group's remaining time, never a fresh budget.
                    remaining = effective_timeout - (time.perf_counter() - started_at)
                    if diagnostics is not None:
                        remaining = min(remaining, diagnostics.deadline - diagnostics.clock())
                    if remaining <= 0:
                        raise TimeoutError('Provider budget exhausted before request.')
                    timeout = httpx.Timeout(remaining, connect=min(5.0, remaining))
                    if diagnostics is not None:
                        diagnostics.calls[-1]['transport_attempts'] = attempt + 1
                    try:
                        async with httpx.AsyncClient(
                            base_url=self._base_url,
                            timeout=timeout,
                            transport=self._transport,
                        ) as client:
                            with stage(f'provider_call_{diagnostics.attempt if diagnostics else 1}_ms'):
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

                    if "format" in payload and not response.is_success:
                        try:
                            message = response.json().get("error", "")
                        except (ValueError, AttributeError):
                            message = ""
                        if isinstance(message, str) and any(marker in message.lower() for marker in ("context size", "context length", "context shift", "input length")):
                            raise AIContextLimitError("The runtime rejected the extraction context; no retry.")
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
                        capture_structured="format" in payload,
                    )
        except TimeoutError as exc:
            if diagnostics is not None and diagnostics.clock() >= diagnostics.deadline:
                raise
            raise AITimeoutError("Ollama did not respond before the timeout.") from exc
        finally:
            if diagnostics is not None and diagnostics.calls:
                diagnostics.calls[-1]['actual_provider_duration_ms'] = max(0, time.perf_counter() - started_at) * 1000

        raise AIProviderError("Ollama request did not complete.")

    def _parse_response(
        self,
        response: httpx.Response,
        *,
        elapsed_seconds: float,
        capture_structured: bool = False,
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
            done_reason=payload.get("done_reason") if payload.get("done_reason") in ("stop", "length") else "unknown",
            prompt_eval_duration_ns=self._optional_non_negative_int(payload, "prompt_eval_duration"),
            eval_duration_ns=self._optional_non_negative_int(payload, "eval_duration"),
            done=payload.get("done") is True,
        )
        diagnostics = CURRENT.get()
        if diagnostics is not None and capture_structured and diagnostics.calls:
            from dataclasses import asdict
            safe_metrics = asdict(self.last_metrics)
            safe_metrics.pop('model', None)
            diagnostics.calls[-1].update(safe_metrics)
        # Durable private checkpoint before context/content/JSON/schema acceptance.
        # Nothing is retained by default; no logging of provider content.
        message = payload.get("message")
        if (capture_structured and self.structured_response_observer is not None
                and isinstance(message, dict) and isinstance(message.get("content"), str)):
            self.structured_response_observer(message["content"], self.last_metrics)
        logger.info(
            "Ollama generation completed model=%s prompt_tokens=%s output_tokens=%s "
            "context_ratio=%s elapsed_seconds=%.3f done_reason=%s",
            self._model,
            prompt_eval_count,
            eval_count,
            f"{context_ratio:.3f}" if context_ratio is not None else "unknown",
            elapsed_seconds,
            payload.get("done_reason") if payload.get("done_reason") in ("stop", "length") else "unknown",
        )
        if capture_structured:
            if payload.get("done_reason") == "length" or (eval_count is not None and eval_count > self._num_predict):
                raise AIOutputBudgetExceededError("Structured extraction exhausted its output budget.")
            if payload.get("done_reason") != "stop":
                raise AIResponseValidationError("Structured extraction did not stop normally.")
            if (prompt_eval_count is not None and self.last_accounting is not None
                and prompt_eval_count > self.last_accounting.prompt_tokens + self.last_accounting.special_tokens + self._safety_margin):
                raise AIContextLimitError("Runtime prompt accounting differs from extraction preflight.")
            if payload.get("context_shift") or payload.get("truncated"):
                raise AIContextLimitError("Runtime reported source context loss.")
            if self.last_accounting is None:
                if prompt_eval_count is None or eval_count is None:
                    raise AITokenAccountingUnavailableError("Runtime did not provide bounded extraction accounting.")
                if prompt_eval_count + eval_count + self._safety_margin > self._num_ctx:
                    raise AIContextLimitError("Runtime extraction context exceeded its safe budget.")
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
