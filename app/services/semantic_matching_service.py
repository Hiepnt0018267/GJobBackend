"""Provider-neutral semantic CV/JD matching over canonical text."""

import math
from collections.abc import Sequence

from app.embeddings import (
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingProvider,
    EmbeddingValidationError,
)
from app.embeddings.factory import get_embedding_provider
from app.schemas.matching import (
    CanonicalCVMatchingInput,
    CanonicalJobMatchingInput,
    SemanticMatchingResult,
)


SEMANTIC_MATCHING_VERSION = "semantic-v1"
_COSINE_BOUNDARY_EPSILON = 1e-12


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return raw cosine similarity after strict vector validation."""

    left_values = _validate_vector(left, label="left")
    right_values = _validate_vector(right, label="right")
    if len(left_values) != len(right_values):
        raise EmbeddingDimensionMismatchError(
            "Cannot compare embedding vectors with different dimensions."
        )

    left_norm = math.sqrt(math.fsum(value * value for value in left_values))
    right_norm = math.sqrt(math.fsum(value * value for value in right_values))
    if left_norm == 0.0 or right_norm == 0.0:
        raise EmbeddingValidationError("Cannot compare a zero-norm embedding vector.")

    similarity = math.fsum(
        left_value * right_value
        for left_value, right_value in zip(left_values, right_values, strict=True)
    ) / (left_norm * right_norm)
    return _enforce_cosine_range(similarity)


def _enforce_cosine_range(similarity: float) -> float:
    """Clamp only machine-scale boundary drift; reject material violations."""

    if not math.isfinite(similarity):
        raise EmbeddingValidationError("Cosine similarity is not finite.")
    if similarity > 1.0 and similarity <= 1.0 + _COSINE_BOUNDARY_EPSILON:
        return 1.0
    if similarity < -1.0 and similarity >= -1.0 - _COSINE_BOUNDARY_EPSILON:
        return -1.0
    if similarity < -1.0 or similarity > 1.0:
        raise EmbeddingValidationError("Cosine similarity is outside its valid range.")
    return similarity


def _validate_vector(vector: Sequence[float], *, label: str) -> tuple[float, ...]:
    if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
        raise EmbeddingValidationError(f"The {label} embedding must be a vector.")
    if not vector:
        raise EmbeddingValidationError(f"The {label} embedding cannot be empty.")

    values: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EmbeddingValidationError(
                f"The {label} embedding must contain only finite numbers."
            )
        number = float(value)
        if not math.isfinite(number):
            raise EmbeddingValidationError(
                f"The {label} embedding must contain only finite numbers."
            )
        values.append(number)
    return tuple(values)


class SemanticMatchingService:
    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider if provider is not None else get_embedding_provider()

    async def match(
        self,
        cv: CanonicalCVMatchingInput,
        job: CanonicalJobMatchingInput,
    ) -> SemanticMatchingResult:
        if not cv.semantic_text.strip() or not job.semantic_text.strip():
            raise EmbeddingInputError(
                "Canonical CV and job semantic text must both be non-empty."
            )

        batch = await self._provider.embed_many(
            [cv.semantic_text, job.semantic_text]
        )
        if len(batch.vectors) != 2:
            raise EmbeddingValidationError(
                "Semantic matching requires exactly two embedding vectors."
            )
        cv_vector, job_vector = batch.vectors
        if len(cv_vector) != len(job_vector):
            raise EmbeddingDimensionMismatchError(
                "CV and job embedding dimensions do not match."
            )
        if batch.dimensions != len(cv_vector):
            raise EmbeddingValidationError(
                "Embedding dimension metadata does not match the vectors."
            )

        return SemanticMatchingResult(
            cv_id=cv.cv_id,
            job_id=job.job_id,
            semantic_similarity=cosine_similarity(cv_vector, job_vector),
            provider=batch.provider,
            model=batch.model,
            dimensions=batch.dimensions,
            engine_version=SEMANTIC_MATCHING_VERSION,
        )
