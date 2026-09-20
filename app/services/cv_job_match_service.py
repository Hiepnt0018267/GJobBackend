"""Authorization-aware orchestration for persisted CV/job matching."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings import (
    EmbeddingError,
    EmbeddingInputTooLongError,
    EmbeddingProviderUnavailableError,
)
from app.models.cv_job_match import CVJobMatch
from app.models.user import User
from app.repositories.cv_job_match_repository import CVJobMatchRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.recruiter_application_repository import (
    RecruiterApplicationRepository,
)
from app.schemas.matching import (
    BaselineMatchComponentResponse,
    BaselineMatchResult,
    CVJobMatchResponse,
    CanonicalCVMatchingInput,
    CanonicalJobMatchingInput,
    MatchComponentErrorCode,
    MatchComponentStatus,
    SemanticMatchComponentResponse,
    SemanticMatchingResult,
)
from app.services.baseline_matching_engine import (
    BASELINE_MATCHING_VERSION,
    BaselineMatchingEngine,
    InsufficientMatchingSignalsError,
)
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job
from app.services.matching_input_service import (
    CVNotReadyForMatchingError,
    JobNotReadyForMatchingError,
    MatchingInputNotFoundError,
    MatchingInputService,
)
from app.services.semantic_matching_service import (
    SEMANTIC_MATCHING_VERSION,
    SemanticMatchingService,
)


class CVJobMatchService:
    def __init__(
        self,
        db: Session,
        *,
        baseline_engine: BaselineMatchingEngine | None = None,
        semantic_service: SemanticMatchingService | None = None,
        expected_provider: str | None = None,
        expected_model: str | None = None,
    ) -> None:
        self.db = db
        self.match_repository = CVJobMatchRepository(db)
        self.cv_repository = CVRepository(db)
        self.recruiter_application_repository = RecruiterApplicationRepository(db)
        self.input_service = MatchingInputService(db)
        self.baseline_engine = (
            baseline_engine if baseline_engine is not None else BaselineMatchingEngine()
        )
        self.semantic_service = (
            semantic_service if semantic_service is not None else SemanticMatchingService()
        )
        self.expected_provider = (
            expected_provider or settings.embedding_provider
        ).strip().lower()
        self.expected_model = (expected_model or settings.embedding_model).strip()

    async def match_for_candidate(
        self,
        current_user: User,
        cv_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> CVJobMatchResponse:
        self._authorize_candidate(current_user.id, cv_id)
        return await self._match_pair(
            cv_id,
            job_id,
            require_approved=True,
            candidate_id=current_user.id,
        )

    async def match_for_recruiter_application(
        self,
        current_user: User,
        application_id: uuid.UUID,
    ) -> CVJobMatchResponse:
        cv_id, job_id = self._authorize_recruiter_application(
            current_user.id,
            application_id,
        )
        return await self._match_pair(
            cv_id,
            job_id,
            require_approved=False,
            recruiter_id=current_user.id,
            application_id=application_id,
        )

    async def _match_pair(
        self,
        cv_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        require_approved: bool,
        candidate_id: uuid.UUID | None = None,
        recruiter_id: uuid.UUID | None = None,
        application_id: uuid.UUID | None = None,
    ) -> CVJobMatchResponse:
        cv_input, job_input = self._build_inputs(
            cv_id,
            job_id,
            require_approved=require_approved,
        )
        cv_fingerprint = fingerprint_cv(cv_input)
        job_fingerprint = fingerprint_job(job_input)
        record = self.match_repository.get_by_pair(cv_id, job_id)
        if record is not None and self._is_fresh(
            record,
            cv_fingerprint=cv_fingerprint,
            job_fingerprint=job_fingerprint,
        ):
            try:
                response = self._response_from_record(record, cached=True)
            except (ValidationError, ValueError):
                pass
            else:
                self.match_repository.rollback()
                return response

        # Release the read transaction before the external embedding call.
        self.match_repository.rollback()
        baseline = self._compute_baseline(cv_input, job_input)
        try:
            semantic_result = await self.semantic_service.match(cv_input, job_input)
        except EmbeddingError as exc:
            return self._partial_failure_response(
                cv_id,
                job_id,
                baseline,
                exc,
            )

        computed_at = datetime.now(timezone.utc)
        try:
            if not self.match_repository.lock_sources(cv_id, job_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="CV or job not found.",
                )
            self.db.expire_all()
            self._reauthorize(
                cv_id=cv_id,
                job_id=job_id,
                candidate_id=candidate_id,
                recruiter_id=recruiter_id,
                application_id=application_id,
            )
            current_cv, current_job = self._build_inputs(
                cv_id,
                job_id,
                require_approved=require_approved,
            )
            if (
                fingerprint_cv(current_cv) != cv_fingerprint
                or fingerprint_job(current_job) != job_fingerprint
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Matching inputs changed during computation. Please retry.",
                )

            persisted = self.match_repository.upsert(
                {
                    "id": uuid.uuid4(),
                    "cv_id": cv_id,
                    "job_id": job_id,
                    "baseline_status": baseline.status.value,
                    "baseline_result": (
                        baseline.result.model_dump(mode="json")
                        if baseline.result is not None
                        else None
                    ),
                    "semantic_similarity": semantic_result.semantic_similarity,
                    "embedding_provider": semantic_result.provider,
                    "embedding_model": semantic_result.model,
                    "embedding_model_config": self.expected_model,
                    "embedding_dimensions": semantic_result.dimensions,
                    "baseline_engine_version": BASELINE_MATCHING_VERSION,
                    "semantic_engine_version": SEMANTIC_MATCHING_VERSION,
                    "cv_fingerprint": cv_fingerprint,
                    "job_fingerprint": job_fingerprint,
                    "computed_at": computed_at,
                    "created_at": computed_at,
                    "updated_at": computed_at,
                }
            )
            self.match_repository.commit()
            return self._response_from_record(persisted, cached=False)
        except Exception:
            self.match_repository.rollback()
            raise

    def _build_inputs(
        self,
        cv_id: uuid.UUID,
        job_id: uuid.UUID,
        *,
        require_approved: bool,
    ) -> tuple[CanonicalCVMatchingInput, CanonicalJobMatchingInput]:
        try:
            return (
                self.input_service.build_cv_input(cv_id),
                self.input_service.build_job_input(
                    job_id,
                    require_approved=require_approved,
                ),
            )
        except MatchingInputNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV or job not found.",
            ) from exc
        except CVNotReadyForMatchingError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except JobNotReadyForMatchingError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

    def _authorize_candidate(
        self,
        candidate_id: uuid.UUID,
        cv_id: uuid.UUID,
    ) -> None:
        if self.cv_repository.get_for_candidate(cv_id, candidate_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV not found.",
            )

    def _authorize_recruiter_application(
        self,
        recruiter_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        application = self.recruiter_application_repository.get_owned_application(
            application_id,
            recruiter_id,
        )
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )
        if application.cv.candidate_id != application.candidate_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application CV ownership is inconsistent.",
            )
        return application.cv_id, application.job_id

    def _reauthorize(
        self,
        *,
        cv_id: uuid.UUID,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID | None,
        recruiter_id: uuid.UUID | None,
        application_id: uuid.UUID | None,
    ) -> None:
        if candidate_id is not None:
            self._authorize_candidate(candidate_id, cv_id)
            return
        if recruiter_id is None or application_id is None:
            raise RuntimeError("Missing recruiter matching context.")
        current_cv_id, current_job_id = self._authorize_recruiter_application(
            recruiter_id,
            application_id,
        )
        if current_cv_id != cv_id or current_job_id != job_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application matching context changed during computation. Please retry.",
            )

    def _compute_baseline(
        self,
        cv: CanonicalCVMatchingInput,
        job: CanonicalJobMatchingInput,
    ) -> BaselineMatchComponentResponse:
        try:
            result = self.baseline_engine.match(cv, job)
        except InsufficientMatchingSignalsError:
            return BaselineMatchComponentResponse(
                status=MatchComponentStatus.INSUFFICIENT_SIGNALS,
                error_code=MatchComponentErrorCode.INSUFFICIENT_MATCHING_SIGNALS,
            )
        return BaselineMatchComponentResponse(
            status=MatchComponentStatus.AVAILABLE,
            result=result,
        )

    def _is_fresh(
        self,
        record: CVJobMatch,
        *,
        cv_fingerprint: str,
        job_fingerprint: str,
    ) -> bool:
        return (
            record.cv_fingerprint == cv_fingerprint
            and record.job_fingerprint == job_fingerprint
            and record.baseline_engine_version == BASELINE_MATCHING_VERSION
            and record.semantic_engine_version == SEMANTIC_MATCHING_VERSION
            and record.embedding_provider.casefold() == self.expected_provider.casefold()
            and record.embedding_model_config == self.expected_model
            and record.embedding_dimensions > 0
        )

    @staticmethod
    def _response_from_record(
        record: CVJobMatch,
        *,
        cached: bool,
    ) -> CVJobMatchResponse:
        baseline_status = MatchComponentStatus(record.baseline_status)
        baseline_result = (
            BaselineMatchResult.model_validate(record.baseline_result)
            if record.baseline_result is not None
            else None
        )
        baseline_error = (
            MatchComponentErrorCode.INSUFFICIENT_MATCHING_SIGNALS
            if baseline_status == MatchComponentStatus.INSUFFICIENT_SIGNALS
            else None
        )
        semantic_result = SemanticMatchingResult(
            cv_id=record.cv_id,
            job_id=record.job_id,
            semantic_similarity=record.semantic_similarity,
            provider=record.embedding_provider,
            model=record.embedding_model,
            dimensions=record.embedding_dimensions,
            engine_version=record.semantic_engine_version,
        )
        return CVJobMatchResponse(
            cv_id=record.cv_id,
            job_id=record.job_id,
            baseline=BaselineMatchComponentResponse(
                status=baseline_status,
                result=baseline_result,
                error_code=baseline_error,
            ),
            semantic=SemanticMatchComponentResponse(
                status=MatchComponentStatus.AVAILABLE,
                result=semantic_result,
            ),
            baseline_engine_version=record.baseline_engine_version,
            semantic_engine_version=record.semantic_engine_version,
            computed_at=record.computed_at,
            cached=cached,
        )

    @staticmethod
    def _partial_failure_response(
        cv_id: uuid.UUID,
        job_id: uuid.UUID,
        baseline: BaselineMatchComponentResponse,
        error: EmbeddingError,
    ) -> CVJobMatchResponse:
        if isinstance(error, EmbeddingInputTooLongError):
            error_code = MatchComponentErrorCode.EMBEDDING_INPUT_TOO_LONG
        elif isinstance(error, EmbeddingProviderUnavailableError):
            error_code = MatchComponentErrorCode.EMBEDDING_PROVIDER_UNAVAILABLE
        else:
            error_code = MatchComponentErrorCode.EMBEDDING_FAILED
        return CVJobMatchResponse(
            cv_id=cv_id,
            job_id=job_id,
            baseline=baseline,
            semantic=SemanticMatchComponentResponse(
                status=MatchComponentStatus.UNAVAILABLE,
                error_code=error_code,
            ),
            baseline_engine_version=BASELINE_MATCHING_VERSION,
            semantic_engine_version=SEMANTIC_MATCHING_VERSION,
            computed_at=datetime.now(timezone.utc),
            cached=False,
        )
