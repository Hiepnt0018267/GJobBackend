"""Provider contract and normalized embedding response."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmbeddingBatchResult:
    vectors: tuple[tuple[float, ...], ...]
    provider: str
    model: str
    dimensions: int


class EmbeddingProvider(Protocol):
    async def embed_many(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        """Embed texts in one ordered provider request."""
