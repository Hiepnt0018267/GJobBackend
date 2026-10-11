"""Total deadline and correction pass budget tests for CVStructuredExtractionService.

Rules verified:
  §35 correction skipped when deadline nearly expired
  §36 total deadline caps entire operation
All tests use FakeAIProvider and monkeypatch -- no live model, no DB.
"""
import asyncio

import pytest

from app.ai.exceptions import AIResponseValidationError
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_structured_extraction_service import (
    CVExtractionDeadlineError,
    CVStructuredExtractionService,
)
from tests.ai.fake_provider import FakeAIProvider


VALID_PAYLOAD = {
    "personal_info": {"full_name": "Test Candidate"},
    "educations": [],
    "experiences": [],
    "skills": [],
    "projects": [],
    "certificates": [],
    "languages": [],
}


# ---------------------------------------------------------------------------
# §35 -- Correction skipped when deadline nearly expired
# ---------------------------------------------------------------------------

def test_correction_skipped_when_deadline_nearly_expired(monkeypatch) -> None:
    """If elapsed time leaves less than correction_min seconds, correction must NOT start."""
    call_count = 0
    clock = [0.0]

    class FirstFailProvider(FakeAIProvider):
        async def generate_structured(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            clock[0] = 15.0
            return {'skills':[{'name':'Python','level':'advanced'}]}

    # Use generous total deadline and correction_min; mock elapsed so guard fires.
    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_total_timeout_seconds",
        30.0,
    )
    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_correction_min_seconds",
        20.0,
    )

    # Fake time: started_at=0; at the guard check (attempt=1), elapsed=15 s.
    # 15 >= 30 - 20 = 10 -> correction blocked.

    import app.services.cv_structured_extraction_service as svc_module
    monkeypatch.setattr(svc_module.time, "perf_counter", lambda: clock[0])

    service = CVStructuredExtractionService(
        provider=FirstFailProvider(),
        max_schema_retries=1,
    )

    with pytest.raises(CVExtractionDeadlineError, match="Insufficient time"):
        asyncio.run(service.extract_from_text("CV text"))

    assert call_count == 1, "Provider must be called exactly once; correction must not start"


def test_correction_allowed_when_sufficient_time_remains(monkeypatch) -> None:
    """If enough time remains, a correction pass must be allowed to start."""
    call_count = 0
    clock = [0.0]

    class FirstFailThenSucceedProvider(FakeAIProvider):
        async def generate_structured(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                clock[0] = 5.0
                return {'skills':[{'name':'Python','level':'advanced'}]}
            return {'repairs':[{'path':['skills',0,'level'],'value':'ADVANCED'}]}

    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_total_timeout_seconds",
        60.0,
    )
    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_correction_min_seconds",
        20.0,
    )

    # started_at=0; at correction guard check (attempt=1), elapsed=5 s.
    # 5 < 60 - 20 = 40 -> correction allowed.
    import app.services.cv_structured_extraction_service as svc_module
    monkeypatch.setattr(svc_module.time, "perf_counter", lambda: clock[0])

    fake = FirstFailThenSucceedProvider()
    service = CVStructuredExtractionService(
        provider=fake, repair_provider=fake,
        max_schema_retries=1,
    )
    result = asyncio.run(service.extract_from_text("CV text"))

    assert call_count == 2, "Provider must be called twice: first attempt + correction"
    assert isinstance(result, StructuredCVExtractionResult)


# ---------------------------------------------------------------------------
# §36 -- Total deadline caps entire operation
# ---------------------------------------------------------------------------

def test_total_deadline_caps_entire_operation(monkeypatch) -> None:
    """asyncio.timeout must fire if the provider takes longer than total_deadline."""

    class SlowProvider(FakeAIProvider):
        async def generate_structured(self, *args, **kwargs):
            await asyncio.sleep(60)
            return VALID_PAYLOAD

    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_total_timeout_seconds",
        0.05,
    )
    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_correction_min_seconds",
        0.02,
    )

    service = CVStructuredExtractionService(provider=SlowProvider())

    with pytest.raises(CVExtractionDeadlineError, match="total time budget"):
        asyncio.run(service.extract_from_text("CV text"))


# ---------------------------------------------------------------------------
# Normal flow: deadline not exceeded -> success
# ---------------------------------------------------------------------------

def test_deadline_not_exceeded_returns_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_total_timeout_seconds",
        30.0,
    )
    monkeypatch.setattr(
        "app.services.cv_structured_extraction_service.settings.cv_extraction_correction_min_seconds",
        10.0,
    )

    service = CVStructuredExtractionService(
        provider=FakeAIProvider(structured_response=VALID_PAYLOAD)
    )
    result = asyncio.run(service.extract_from_text("Test CV candidate"))

    assert isinstance(result, StructuredCVExtractionResult)
    assert result.personal_info.full_name == "Test Candidate"
