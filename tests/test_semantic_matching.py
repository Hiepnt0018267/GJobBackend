"""Offline semantic matching tests with a provider fake."""

import asyncio
import math
import uuid
from collections.abc import Sequence

import pytest

from app.embeddings import (
    EmbeddingBatchResult,
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingValidationError,
)
from app.models.job import JobStatus
from app.schemas.matching import (
    CanonicalCVMatchingInput,
    CanonicalJobMatchingInput,
    CanonicalSalaryMetadata,
    SemanticMatchingResult,
)
from app.services.semantic_matching_service import (
    SEMANTIC_MATCHING_VERSION,
    SemanticMatchingService,
    _enforce_cosine_range,
    cosine_similarity,
)


CV_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class FakeEmbeddingProvider:
    def __init__(self, result: EmbeddingBatchResult) -> None:
        self.result = result
        self.calls: list[list[str]] = []

    async def embed_many(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        self.calls.append(list(texts))
        return self.result


def _cv(text: str = "Python FastAPI backend") -> CanonicalCVMatchingInput:
    return CanonicalCVMatchingInput(
        cv_id=CV_ID,
        skills=[],
        experiences=[],
        educations=[],
        projects=[],
        certificates=[],
        languages=[],
        semantic_text=text,
    )


def _job(text: str = "Backend engineer with Python") -> CanonicalJobMatchingInput:
    return CanonicalJobMatchingInput(
        job_id=JOB_ID,
        title="Backend Engineer",
        description="Build backend systems",
        skills=[],
        status=JobStatus.APPROVED,
        salary=CanonicalSalaryMetadata(currency="VND"),
        vacancies=1,
        semantic_text=text,
    )


def _result(
    vectors: tuple[tuple[float, ...], ...] = ((1.0, 0.0), (0.5, 0.5)),
    *,
    dimensions: int = 2,
) -> EmbeddingBatchResult:
    return EmbeddingBatchResult(
        vectors=vectors,
        provider="fake",
        model="synthetic-embedding",
        dimensions=dimensions,
    )


def _match(provider: FakeEmbeddingProvider, cv_text: str = "cv", job_text: str = "job"):
    return asyncio.run(
        SemanticMatchingService(provider).match(_cv(cv_text), _job(job_text))
    )


def test_service_embeds_exact_canonical_texts_once_in_cv_job_order() -> None:
    provider = FakeEmbeddingProvider(_result())

    result = _match(provider, "  exact cv text  ", "exact job\ntext")

    assert provider.calls == [["  exact cv text  ", "exact job\ntext"]]
    assert isinstance(result, SemanticMatchingResult)
    assert result.cv_id == CV_ID
    assert result.job_id == JOB_ID
    assert result.semantic_similarity == pytest.approx(math.sqrt(0.5))
    assert result.provider == "fake"
    assert result.model == "synthetic-embedding"
    assert result.dimensions == 2
    assert result.engine_version == SEMANTIC_MATCHING_VERSION


@pytest.mark.parametrize(("cv_text", "job_text"), [("", "job"), ("cv", " "), ("\t", "\n")])
def test_blank_canonical_text_fails_before_provider(
    cv_text: str,
    job_text: str,
) -> None:
    provider = FakeEmbeddingProvider(_result())

    with pytest.raises(EmbeddingInputError):
        _match(provider, cv_text, job_text)
    assert provider.calls == []


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ([1.0, 2.0], [1.0, 2.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], -1.0),
        ([3.0, 4.0], [4.0, 3.0], 0.96),
    ],
)
def test_cosine_similarity_returns_raw_expected_value(
    left: list[float],
    right: list[float],
    expected: float,
) -> None:
    assert cosine_similarity(left, right) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("left", "right", "error_type"),
    [
        ([], [1.0], EmbeddingValidationError),
        ([1.0], [], EmbeddingValidationError),
        ([1.0], [1.0, 2.0], EmbeddingDimensionMismatchError),
        ([0.0, 0.0], [1.0, 1.0], EmbeddingValidationError),
        ([1.0, 1.0], [0.0, 0.0], EmbeddingValidationError),
        ([math.nan], [1.0], EmbeddingValidationError),
        ([math.inf], [1.0], EmbeddingValidationError),
        ([True], [1.0], EmbeddingValidationError),
    ],
)
def test_cosine_rejects_invalid_vectors(
    left: list[float],
    right: list[float],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        cosine_similarity(left, right)


def test_cosine_range_only_clamps_tiny_floating_point_drift() -> None:
    assert _enforce_cosine_range(1.0 + 5e-13) == 1.0
    assert _enforce_cosine_range(-1.0 - 5e-13) == -1.0
    with pytest.raises(EmbeddingValidationError):
        _enforce_cosine_range(1.01)
    with pytest.raises(EmbeddingValidationError):
        _enforce_cosine_range(-1.01)


@pytest.mark.parametrize(
    ("batch", "error_type"),
    [
        (_result(((1.0, 0.0),), dimensions=2), EmbeddingValidationError),
        (_result(((1.0,), (1.0,), (1.0,)), dimensions=1), EmbeddingValidationError),
        (_result(((1.0,), (1.0, 0.0)), dimensions=1), EmbeddingDimensionMismatchError),
        (_result(((1.0, 0.0), (1.0, 0.0)), dimensions=3), EmbeddingValidationError),
    ],
)
def test_service_revalidates_provider_batch_contract(
    batch: EmbeddingBatchResult,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        _match(FakeEmbeddingProvider(batch))


def test_repeated_matching_is_deterministic() -> None:
    provider = FakeEmbeddingProvider(_result())
    service = SemanticMatchingService(provider)
    cv = _cv()
    job = _job()

    results = [asyncio.run(service.match(cv, job)) for _ in range(5)]

    assert all(result == results[0] for result in results)
    assert provider.calls == [[cv.semantic_text, job.semantic_text]] * 5


def test_non_semantic_metadata_cannot_change_embedding_input() -> None:
    provider = FakeEmbeddingProvider(_result())
    service = SemanticMatchingService(provider)
    cv = _cv("same privacy-filtered cv text")
    job = _job("same privacy-filtered job text")
    changed_cv = cv.model_copy(update={"location": None})
    changed_job = job.model_copy(
        update={
            "title": "Different display title",
            "vacancies": 99,
            "salary": CanonicalSalaryMetadata(
                minimum=99_000_000,
                maximum=120_000_000,
                currency="VND",
            ),
        }
    )

    asyncio.run(service.match(cv, job))
    asyncio.run(service.match(changed_cv, changed_job))

    assert provider.calls == [
        ["same privacy-filtered cv text", "same privacy-filtered job text"],
        ["same privacy-filtered cv text", "same privacy-filtered job text"],
    ]


def test_result_is_json_serializable_and_contains_no_vectors_or_private_fields() -> None:
    result = _match(FakeEmbeddingProvider(_result()))
    payload = result.model_dump(mode="json")

    assert set(payload) == {
        "cv_id",
        "job_id",
        "semantic_similarity",
        "provider",
        "model",
        "dimensions",
        "engine_version",
    }
    assert "vector" not in str(payload).casefold()
    assert -1.0 <= result.semantic_similarity <= 1.0
