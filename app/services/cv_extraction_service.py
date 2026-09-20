import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import AIProviderError
from app.core.config import settings
from app.models.cv import CV, CVSourceType
from app.models.cv_extraction import CVExtraction, CVExtractionStatus
from app.models.user import User
from app.repositories.cv_extraction_repository import CVExtractionRepository
from app.repositories.cv_repository import CVRepository
from app.schemas.cv import CVResponse
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.cv_extraction_api import (
    CVExtractionConfirmationResponse,
    CVExtractionResponse,
)
from app.services.cv_structured_extraction_service import (
    CVAIRateLimitError,
    CVAIProviderRequestError,
    CVAIProviderUnavailableError,
    CVExtractionValidationError,
    CVStructuredExtractionError,
    CVStructuredExtractionService,
)
from app.services.cv_text_extraction_service import UploadedCVTextSource
from app.services.document_text_extractor import DocumentExtractionError


class CVExtractionFailureCode:
    DOCUMENT_EXTRACTION_FAILED = "DOCUMENT_EXTRACTION_FAILED"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_PROVIDER_REQUEST_INVALID = "AI_PROVIDER_REQUEST_INVALID"
    AI_RATE_LIMITED = "AI_RATE_LIMITED"
    AI_RESPONSE_INVALID = "AI_RESPONSE_INVALID"
    UNKNOWN_EXTRACTION_FAILURE = "UNKNOWN_EXTRACTION_FAILURE"


class CandidateCVExtractionService:
    def __init__(
        self,
        db: Session,
        structured_extractor: CVStructuredExtractionService | None = None,
    ) -> None:
        self.cv_repository = CVRepository(db)
        self.extraction_repository = CVExtractionRepository(db)
        self.structured_extractor = structured_extractor

    def _owned_cv_or_404(self, current_user: User, cv_id: uuid.UUID) -> CV:
        cv = self.cv_repository.get_for_candidate(cv_id, current_user.id)
        if cv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV not found.",
            )
        return cv

    def _owned_cv_for_update_or_404(
        self, current_user: User, cv_id: uuid.UUID
    ) -> CV:
        cv = self.cv_repository.get_for_candidate_for_update(cv_id, current_user.id)
        if cv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV not found.",
            )
        return cv

    @staticmethod
    def _response(extraction: CVExtraction) -> CVExtractionResponse:
        return CVExtractionResponse.model_validate(extraction)

    def get_latest(
        self, current_user: User, cv_id: uuid.UUID
    ) -> CVExtractionResponse:
        cv = self._owned_cv_or_404(current_user, cv_id)
        extraction = self.extraction_repository.get_latest_for_cv(cv.id)
        if extraction is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV extraction not found.",
            )
        return self._response(extraction)

    async def trigger(
        self, current_user: User, cv_id: uuid.UUID
    ) -> tuple[CVExtractionResponse, bool]:
        cv = self._owned_cv_for_update_or_404(current_user, cv_id)
        if cv.source_type != CVSourceType.UPLOADED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only uploaded CVs support AI extraction.",
            )

        active = self.extraction_repository.get_active_for_cv(cv.id)
        if active is not None:
            return self._response(active), False

        extraction_source = UploadedCVTextSource(
            source_type=cv.source_type,
            storage_key=cv.storage_key,
            mime_type=cv.mime_type,
            original_filename=cv.original_filename,
        )

        now = datetime.now(timezone.utc)
        extraction = CVExtraction(
            id=uuid.uuid4(),
            cv_id=cv.id,
            provider=settings.ai_provider.strip().lower(),
            model=settings.gemini_model,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        extraction_id = extraction.id
        try:
            self.extraction_repository.create_processing(extraction)
        except IntegrityError:
            self.extraction_repository.rollback()
            active = self.extraction_repository.get_active_for_cv(cv.id)
            if active is None:
                raise
            return self._response(active), False

        try:
            extractor = (
                self.structured_extractor
                if self.structured_extractor is not None
                else CVStructuredExtractionService()
            )
            result = await extractor.extract_uploaded_cv(extraction_source)
        except DocumentExtractionError as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.DOCUMENT_EXTRACTION_FAILED,
                "Không thể trích xuất nội dung từ tệp CV đã tải lên.",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The uploaded CV document could not be extracted.",
            ) from exc
        except CVExtractionValidationError as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.AI_RESPONSE_INVALID,
                "Kết quả trích xuất AI không đúng cấu trúc yêu cầu.",
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI provider returned an invalid extraction result.",
            ) from exc
        except CVAIProviderRequestError as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.AI_PROVIDER_REQUEST_INVALID,
                "Hệ thống AI chưa thể xử lý CV do cấu hình yêu cầu không tương thích.",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The AI integration could not process the extraction request.",
            ) from exc
        except CVAIRateLimitError as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.AI_RATE_LIMITED,
                "Hệ thống AI đang tạm thời giới hạn lượt xử lý. Vui lòng thử lại sau.",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": CVExtractionFailureCode.AI_RATE_LIMITED,
                    "message": "CV extraction is temporarily rate limited.",
                },
            ) from exc
        except (CVAIProviderUnavailableError, AIProviderError) as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.AI_PROVIDER_UNAVAILABLE,
                "Dịch vụ trích xuất AI hiện không khả dụng.",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="CV extraction is temporarily unavailable.",
            ) from exc
        except CVStructuredExtractionError as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.AI_RESPONSE_INVALID,
                "Dữ liệu đầu vào hoặc kết quả trích xuất AI không hợp lệ.",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The CV could not be processed for extraction.",
            ) from exc
        except Exception as exc:
            self._persist_failure(
                extraction_id,
                CVExtractionFailureCode.UNKNOWN_EXTRACTION_FAILURE,
                "Quá trình trích xuất CV thất bại do lỗi không xác định.",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CV extraction failed.",
            ) from exc

        persisted = self.extraction_repository.mark_succeeded(
            extraction_id,
            result.model_dump(mode="json"),
            datetime.now(timezone.utc),
        )
        return self._response(persisted), True

    def confirm(
        self,
        current_user: User,
        cv_id: uuid.UUID,
        extraction_id: uuid.UUID,
        reviewed_payload: StructuredCVExtractionResult,
    ) -> CVExtractionConfirmationResponse:
        cv = self._owned_cv_for_update_or_404(current_user, cv_id)
        if cv.source_type != CVSourceType.UPLOADED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only uploaded CVs support extraction confirmation.",
            )

        extraction = self.extraction_repository.get_for_cv_for_update(
            extraction_id, cv.id
        )
        if extraction is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV extraction not found.",
            )
        if extraction.status != CVExtractionStatus.SUCCEEDED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only a succeeded extraction can be confirmed.",
            )

        latest = self.extraction_repository.get_latest_for_cv(cv.id)
        if latest is None or latest.id != extraction.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only the latest CV extraction can be confirmed.",
            )
        if extraction.confirmed_at is not None:
            return self._confirmation_response(cv, extraction)

        reviewed_fields = reviewed_payload.model_dump(mode="json")
        cv, extraction = self.extraction_repository.apply_confirmation(
            cv,
            extraction,
            reviewed_fields,
            datetime.now(timezone.utc),
        )
        return self._confirmation_response(cv, extraction)

    @staticmethod
    def _confirmation_response(
        cv: CV, extraction: CVExtraction
    ) -> CVExtractionConfirmationResponse:
        if extraction.confirmed_at is None:
            raise RuntimeError("Confirmed extraction is missing confirmed_at.")
        return CVExtractionConfirmationResponse(
            cv_id=cv.id,
            extraction_id=extraction.id,
            confirmed_at=extraction.confirmed_at,
            cv=CVResponse.model_validate(cv),
        )

    def _persist_failure(
        self,
        extraction_id: uuid.UUID,
        error_code: str,
        failure_reason: str,
    ) -> None:
        self.extraction_repository.mark_failed(
            extraction_id,
            error_code,
            failure_reason,
            datetime.now(timezone.utc),
        )
