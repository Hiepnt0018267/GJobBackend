"""Embedding provider composition root."""

from app.core.config import settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.ollama_provider import OllamaEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.strip().lower()
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    raise ValueError(f"Unsupported embedding provider: {provider}")
