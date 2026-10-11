"""Ollama implementation of the generic embedding provider contract."""

import math
from collections.abc import Sequence
from typing import Any

import httpx

from app.embeddings.base import EmbeddingBatchResult
from app.embeddings.profile import embedding_profile
from app.embeddings.exceptions import (
    EmbeddingDimensionMismatchError,
    EmbeddingInputError,
    EmbeddingInputTooLongError,
    EmbeddingProviderResponseError,
    EmbeddingProviderUnavailableError,
    EmbeddingValidationError,
)


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        num_ctx: int = 8192,
        num_batch: int = 4096,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self.profile=embedding_profile(self.provider_name,model,num_ctx,num_batch)
        self.last_prompt_eval_count=None

    async def embed_many(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        self.last_prompt_eval_count=None
        normalized_texts = list(texts)
        if not normalized_texts:
            raise EmbeddingInputError("At least one text is required for embedding.")
        if any(not isinstance(text, str) or not text.strip() for text in normalized_texts):
            raise EmbeddingInputError("Embedding inputs must be non-empty text.")

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/api/embed",
                    json={
                        "model": self._model,
                        "input": normalized_texts,
                        "truncate": False,
                        "options": {"num_ctx":self.profile['num_ctx'],"num_batch":self.profile['num_batch']},
                    },
                )
        except httpx.RequestError as exc:
            raise EmbeddingProviderUnavailableError(
                "The embedding provider is unavailable."
            ) from exc

        if not response.is_success:
            self._raise_http_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingProviderResponseError(
                "The embedding provider returned unreadable JSON."
            ) from exc

        result=self._validate_response(payload, expected_count=len(normalized_texts))
        count=payload.get('prompt_eval_count')
        if count is not None and (isinstance(count,bool) or not isinstance(count,int) or count<0):
            raise EmbeddingValidationError('Invalid embedding token accounting.')
        self.last_prompt_eval_count=count
        return result

    def _raise_http_error(self, response: httpx.Response) -> None:
        message = ""
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                message = payload["error"].lower()
        except ValueError:
            pass

        length_markers = (
            "context length",
            "context window",
            "input length",
            "too long",
            "token limit",
        )
        if response.status_code in {400, 413, 422} and any(
            marker in message for marker in length_markers
        ):
            raise EmbeddingInputTooLongError(
                "Embedding input exceeds the model context capacity."
            )
        if response.status_code == 404:
            raise EmbeddingProviderUnavailableError(
                "The configured embedding model is unavailable."
            )
        raise EmbeddingProviderResponseError(
            f"The embedding provider returned HTTP {response.status_code}."
        )

    def _validate_response(
        self,
        payload: Any,
        *,
        expected_count: int,
    ) -> EmbeddingBatchResult:
        if not isinstance(payload, dict):
            raise EmbeddingValidationError("Embedding response must be an object.")

        response_model = payload.get("model")
        if not isinstance(response_model, str) or not response_model.strip():
            raise EmbeddingValidationError("Embedding response is missing its model.")

        raw_vectors = payload.get("embeddings")
        if not isinstance(raw_vectors, list):
            raise EmbeddingValidationError("Embedding response is missing vectors.")
        if len(raw_vectors) != expected_count:
            raise EmbeddingValidationError(
                "Embedding response vector count does not match input count."
            )

        vectors: list[tuple[float, ...]] = []
        dimensions: int | None = None
        for raw_vector in raw_vectors:
            if not isinstance(raw_vector, list) or not raw_vector:
                raise EmbeddingValidationError(
                    "Each embedding vector must be a non-empty array."
                )
            vector: list[float] = []
            for value in raw_vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise EmbeddingValidationError(
                        "Embedding vector values must be finite numbers."
                    )
                number = float(value)
                if not math.isfinite(number):
                    raise EmbeddingValidationError(
                        "Embedding vector values must be finite numbers."
                    )
                vector.append(number)

            if dimensions is None:
                dimensions = len(vector)
            elif len(vector) != dimensions:
                raise EmbeddingDimensionMismatchError(
                    "Embedding vectors have inconsistent dimensions."
                )
            vectors.append(tuple(vector))

        if dimensions is None:
            raise EmbeddingValidationError("Embedding response contains no vectors.")
        return EmbeddingBatchResult(
            vectors=tuple(vectors),
            provider=self.provider_name,
            model=response_model.strip(),
            dimensions=dimensions,
        )
