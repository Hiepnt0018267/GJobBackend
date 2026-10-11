"""Eligibility boundary for building canonical CV and Job matching inputs."""

import uuid

from sqlalchemy.orm import Session

from app.models.cv import CVSourceType
from app.models.cv_extraction import CVExtraction, CVExtractionStatus
from app.models.job import JobStatus
from app.repositories.cv_extraction_repository import CVExtractionRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.job_repository import JobRepository
from app.schemas.matching import CanonicalCVMatchingInput, CanonicalJobMatchingInput
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.matching_input_mapper import (
    build_cv_matching_input,
    build_job_matching_input,
)


class MatchingInputNotFoundError(LookupError):
    """Raised when an internal matching resource does not exist."""


class CVNotReadyForMatchingError(RuntimeError):
    """Raised when an uploaded CV has no usable structured representation."""


class JobNotReadyForMatchingError(RuntimeError):
    """Raised when a candidate-facing workflow requests an unapproved job."""


class MatchingInputService:
    def __init__(self, db: Session) -> None:
        self.cv_repository = CVRepository(db)
        self.extraction_repository = CVExtractionRepository(db)
        self.job_repository = JobRepository(db)

    def build_cv_inputs(self, cvs):
        """Batch equivalent of the single-CV policy; failures remain per entity.

        Relations supplied by an already authorized application query. No model,
        file decoding or raw-source adapter is involved.
        """
        uploaded = [cv.id for cv in cvs if cv.source_type == CVSourceType.UPLOADED]
        rows = []
        if uploaded:
            rows = (self.extraction_repository.db.query(CVExtraction)
                    .filter(CVExtraction.cv_id.in_(uploaded))
                    .order_by(CVExtraction.created_at.desc(), CVExtraction.id.desc()).all())
        confirmed = {row.cv_id for row in rows
                     if row.status == CVExtractionStatus.SUCCEEDED and row.confirmed_at is not None}
        successful = {}
        for row in rows:
            if row.status == CVExtractionStatus.SUCCEEDED:
                successful.setdefault(row.cv_id, row)
        results = {}
        for cv in cvs:
            try:
                if cv.source_type != CVSourceType.UPLOADED or cv.id in confirmed:
                    results[cv.id] = build_cv_matching_input(cv)
                elif cv.id in successful and successful[cv.id].structured_result is not None:
                    structured = StructuredCVExtractionResult.model_validate(successful[cv.id].structured_result)
                    results[cv.id] = build_cv_matching_input(cv, structured)
                else:
                    results[cv.id] = CVNotReadyForMatchingError("No usable structured CV.")
            except (ValueError, TypeError) as exc:
                results[cv.id] = exc
        return results

    def build_cv_input(self, cv_id: uuid.UUID) -> CanonicalCVMatchingInput:
        cv = self.cv_repository.get_by_id_for_matching(cv_id)
        if cv is None:
            raise MatchingInputNotFoundError("CV not found.")
        if cv.source_type != CVSourceType.UPLOADED:
            return build_cv_matching_input(cv)

        # Confirmation copies one complete candidate-reviewed representation onto CV.
        # It remains authoritative even if a later automatic/retry attempt succeeds.
        if self.extraction_repository.has_confirmed_for_cv(cv.id):
            return build_cv_matching_input(cv)

        successful = self.extraction_repository.get_latest_successful_for_cv(cv.id)
        if successful is not None and successful.structured_result is not None:
            structured = StructuredCVExtractionResult.model_validate(
                successful.structured_result
            )
            return build_cv_matching_input(cv, structured)

        latest = self.extraction_repository.get_latest_for_cv(cv.id)
        if latest is not None and latest.status == CVExtractionStatus.PROCESSING:
            raise CVNotReadyForMatchingError(
                "Uploaded CV extraction is still processing."
            )
        raise CVNotReadyForMatchingError(
            "Uploaded CV has no usable successful extraction."
        )

    def build_job_input(
        self, job_id: uuid.UUID, *, require_approved: bool = True
    ) -> CanonicalJobMatchingInput:
        job = self.job_repository.get_by_id_for_matching(job_id)
        if job is None:
            raise MatchingInputNotFoundError("Job not found.")
        if require_approved and job.status != JobStatus.APPROVED:
            raise JobNotReadyForMatchingError(
                "Only approved jobs are eligible for candidate-facing matching."
            )
        taxonomy_skills = [link.skill for link in job.skill_links]
        return build_job_matching_input(job, taxonomy_skills)
