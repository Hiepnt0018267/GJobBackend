import random
import re
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from google.genai.errors import APIError
from tenacity import RetryCallState
from tenacity.wait import wait_base


GEMINI_RETRY_MIN_SECONDS = 1.0
GEMINI_RETRY_MAX_SECONDS = 8.0
GEMINI_RETRY_JITTER_SECONDS = 1.0


class TransientAIError(Exception):
    kind = "provider"


class TransientRateLimitError(TransientAIError):
    kind = "rate_limit"

    def __init__(self, retry_after_seconds: float | None) -> None:
        super().__init__("Gemini rate limited")
        self.retry_after_seconds = retry_after_seconds


class TransientTimeoutError(TransientAIError):
    kind = "timeout"


class TransientProviderError(TransientAIError):
    kind = "provider"


def _parse_retry_after_header(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip()
    try:
        return max(0.0, float(normalized))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _structured_retry_delay(details: object) -> float | None:
    if not isinstance(details, dict):
        return None
    error_payload = details.get("error", details)
    if not isinstance(error_payload, dict):
        return None
    metadata = error_payload.get("details")
    if not isinstance(metadata, list):
        return None
    for item in metadata:
        if not isinstance(item, dict):
            continue
        value = item.get("retryDelay")
        if not isinstance(value, str):
            continue
        match = re.fullmatch(r"(\d+(?:\.\d+)?)s", value.strip())
        if match:
            return float(match.group(1))
    return None


def retry_after_seconds(error: APIError) -> float | None:
    """Read provider retry metadata without parsing the raw error message."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    get_header = getattr(headers, "get", None)
    if callable(get_header):
        parsed = _parse_retry_after_header(get_header("Retry-After"))
        if parsed is not None:
            return parsed
    return _structured_retry_delay(getattr(error, "details", None))


class GeminiRetryWait(wait_base):
    """Bounded Retry-After or exponential delay with per-request jitter."""

    def __init__(
        self,
        random_source: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._random_source = random_source

    def delay_for(
        self,
        attempt_number: int,
        error: BaseException | None,
    ) -> float:
        suggested = (
            error.retry_after_seconds
            if isinstance(error, TransientRateLimitError)
            else None
        )
        if suggested is None:
            base = min(
                GEMINI_RETRY_MAX_SECONDS,
                GEMINI_RETRY_MIN_SECONDS * (2 ** max(0, attempt_number - 1)),
            )
        else:
            base = min(
                GEMINI_RETRY_MAX_SECONDS,
                max(GEMINI_RETRY_MIN_SECONDS, suggested),
            )

        jitter_room = min(
            GEMINI_RETRY_JITTER_SECONDS,
            max(0.0, GEMINI_RETRY_MAX_SECONDS - base),
        )
        return base + self._random_source(0.0, jitter_room)

    def __call__(self, retry_state: RetryCallState) -> float:
        error = (
            retry_state.outcome.exception()
            if retry_state.outcome is not None
            else None
        )
        return self.delay_for(retry_state.attempt_number, error)
