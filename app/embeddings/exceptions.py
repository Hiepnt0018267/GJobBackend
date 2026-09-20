"""Safe, provider-neutral embedding failures."""


class EmbeddingError(RuntimeError):
    """Base class for expected embedding failures."""


class EmbeddingInputError(EmbeddingError):
    """The caller supplied input that cannot be embedded."""


class EmbeddingInputTooLongError(EmbeddingInputError):
    """The provider rejected input exceeding its context capacity."""


class EmbeddingProviderUnavailableError(EmbeddingError):
    """The configured provider or model is unavailable."""


class EmbeddingProviderResponseError(EmbeddingError):
    """The provider returned an unsuccessful or unreadable response."""


class EmbeddingValidationError(EmbeddingProviderResponseError):
    """The provider response violates the embedding contract."""


class EmbeddingDimensionMismatchError(EmbeddingValidationError):
    """Vectors do not share one non-zero dimension."""
