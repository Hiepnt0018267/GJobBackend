"""Eligibility boundary for building canonical CV and Job matching inputs."""

import uuid

from sqlalchemy.orm import Session

from app.models.cv import CVSourceType
from app.models.job import JobStatus
from app.repositories.cv_extraction_repository import CVExtractionRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.job_repository import JobRepository
from app.schemas.matching import CanonicalCVMatchingInput, CanonicalJobMatchingInput
from app.services.matching_input_mapper import (
    build_cv_matching_input,
    build_job_matching_input,
)


class MatchingInputNotFoundError(LookupError):
    """Raised when an internal matching resource does not exist."""


class CVNotReadyForMatchingError(RuntimeError):
    """Raised when an uploaded CV has no candidate-confirmed structured data."""


class JobNotReadyForMatchingError(RuntimeError):
    """Raised when a candidate-facing workflow requests an unapproved job."""


class MatchingInputService:
    def __init__(self, db: Session) -> None:
        self.cv_repository = CVRepository(db)
        self.extraction_repository = CVExtractionRepository(db)
        self.job_repository = JobRepository(db)

    def build_cv_input(self, cv_id: uuid.UUID) -> CanonicalCVMatchingInput:
        cv = self.cv_repository.get_by_id_for_matching(cv_id)
        if cv is None:
            raise MatchingInputNotFoundError("CV not found.")
        if (
            cv.source_type == CVSourceType.UPLOADED
            and not self.extraction_repository.has_confirmed_for_cv(cv.id)
        ):
            raise CVNotReadyForMatchingError(
                "Uploaded CV structured data has not been confirmed by the candidate."
            )
        return build_cv_matching_input(cv)

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
