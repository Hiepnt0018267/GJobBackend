"""Provider-neutral text embedding infrastructure."""

from app.embeddings.base import EmbeddingBatchResult, EmbeddingProvider
from app.embeddings.exceptions import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingInputError,
    EmbeddingInputTooLongError,
    EmbeddingProviderResponseError,
    EmbeddingProviderUnavailableError,
    EmbeddingValidationError,
)

__all__ = [
    "EmbeddingBatchResult",
    "EmbeddingDimensionMismatchError",
    "EmbeddingError",
    "EmbeddingInputError",
    "EmbeddingInputTooLongError",
    "EmbeddingProvider",
    "EmbeddingProviderResponseError",
    "EmbeddingProviderUnavailableError",
    "EmbeddingValidationError",
]
