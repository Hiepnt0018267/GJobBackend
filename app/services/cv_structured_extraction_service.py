from pydantic import ValidationError

from app.ai import AIProvider, AIProviderError, AIResponseValidationError, create_ai_provider
from app.ai.exceptions import (
    AIContextLimitError,
    AIRateLimitError,
    AIProviderRequestError,
)
from app.ai.cv_extraction_prompt import (
    CV_EXTRACTION_SYSTEM_INSTRUCTION,
    build_cv_extraction_prompt,
)
from app.core.config import settings
from app.models.cv import CV
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_text_extraction_service import (
    CVTextExtractionService,
    UploadedCVTextSource,
)


class CVStructuredExtractionError(RuntimeError):
    """Base error for safe, non-persistent structured CV extraction."""


class CVStructuredExtractionInputError(CVStructuredExtractionError):
    pass


class CVExtractionValidationError(CVStructuredExtractionError):
    pass


class CVAIProviderUnavailableError(CVStructuredExtractionError):
    pass


class CVAIRateLimitError(CVStructuredExtractionError):
    """Gemini remained rate limited after the bounded retry policy."""

    pass


class CVAIContextLimitError(CVStructuredExtractionError):
    """The selected provider exhausted the configured context window."""

    pass


class CVAIProviderRequestError(CVStructuredExtractionError):
    """The provider rejected GJob's deterministic request configuration."""

    pass


class CVStructuredExtractionService:
    def __init__(
        self,
        provider: AIProvider | None = None,
        text_extraction_service: CVTextExtractionService | None = None,
    ) -> None:
        self.provider = provider if provider is not None else create_ai_provider()
        self.text_extraction_service = (
            text_extraction_service
            if text_extraction_service is not None
            else CVTextExtractionService()
        )

    async def extract_from_text(self, cv_text: str) -> StructuredCVExtractionResult:
        normalized_text = cv_text.strip()
        if not normalized_text:
            raise CVStructuredExtractionInputError("CV text must not be empty.")
        if len(normalized_text) > settings.CV_EXTRACTED_TEXT_MAX_CHARACTERS:
            raise CVStructuredExtractionInputError(
                "CV text exceeds the configured extraction limit."
            )

        try:
            payload = await self.provider.generate_structured(
                prompt=build_cv_extraction_prompt(normalized_text),
                response_schema=StructuredCVExtractionResult,
                system_instruction=CV_EXTRACTION_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )
        except AIResponseValidationError as exc:
            raise CVExtractionValidationError(
                "AI returned invalid structured CV data."
            ) from exc
        except AIProviderRequestError as exc:
            raise CVAIProviderRequestError(
                "The AI provider rejected the structured extraction request."
            ) from exc
        except AIRateLimitError as exc:
            raise CVAIRateLimitError(
                "Structured CV extraction is temporarily rate limited."
            ) from exc
        except AIContextLimitError as exc:
            raise CVAIContextLimitError(
                "CV content exceeds the safe AI context limit."
            ) from exc
        except AIProviderError as exc:
            raise CVAIProviderUnavailableError(
                "Structured CV extraction is temporarily unavailable."
            ) from exc

        try:
            return StructuredCVExtractionResult.model_validate(payload)
        except ValidationError as exc:
            raise CVExtractionValidationError(
                "AI returned data that does not match the CV schema."
            ) from exc

    async def extract_uploaded_cv(
        self, cv: CV | UploadedCVTextSource
    ) -> StructuredCVExtractionResult:
        document = self.text_extraction_service.extract_uploaded_cv(cv)
        return await self.extract_from_text(document.text)
