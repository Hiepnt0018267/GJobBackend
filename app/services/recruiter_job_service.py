"""Recruiter-owned job lifecycle and persistence rules (Task 06A)."""
import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.job import (
    JobCreateRequest, JobUpdateRequest, RecruiterJobListResponse, RecruiterJobResponse,
    RecruiterJobSortOption, validate_effective_salary,
)


class RecruiterJobService:
    def __init__(self, db: Session) -> None:
        self.repository = JobRepository(db)

    @staticmethod
    def _owned_or_404(job_id: uuid.UUID, recruiter_id: uuid.UUID, repository: JobRepository) -> Job:
        job = repository.get_for_recruiter(job_id, recruiter_id)
        if job is None:
            # Deliberately do not reveal a different recruiter's job exists.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    def list_jobs(self, user: User, keyword: str | None, job_status: JobStatus | None,
                  page: int, page_size: int, sort: RecruiterJobSortOption) -> RecruiterJobListResponse:
        items, total = self.repository.get_recruiter_jobs(user.id, keyword, job_status, page, page_size, sort)
        return RecruiterJobListResponse(
            items=[RecruiterJobResponse.model_validate(job) for job in items],
            page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_job(self, user: User, job_id: uuid.UUID) -> Job:
        return self._owned_or_404(job_id, user.id, self.repository)

    def create_job(self, user: User, payload: JobCreateRequest) -> Job:
        job = Job(**payload.model_dump(), recruiter_id=user.id, status=JobStatus.PENDING)
        return self.repository.create(job)

    def update_job(self, user: User, job_id: uuid.UUID, payload: JobUpdateRequest) -> Job:
        job = self.get_job(user, job_id)
        if job.status == JobStatus.CLOSED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Closed jobs cannot be edited.")
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Provide at least one editable field.")
        effective_salary = {
            "salary_type": changes.get("salary_type", job.salary_type),
            "salary_min": changes.get("salary_min", job.salary_min),
            "salary_max": changes.get("salary_max", job.salary_max),
            "salary_fixed": changes.get("salary_fixed", job.salary_fixed),
        }
        try:
            validate_effective_salary(effective_salary)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        for field, value in changes.items():
            setattr(job, field, value)
        # Any editable non-closed state returns to moderation.
        job.status = JobStatus.PENDING
        return self.repository.save(job)

    def delete_job(self, user: User, job_id: uuid.UUID) -> None:
        job = self.get_job(user, job_id)
        if job.status not in (JobStatus.PENDING, JobStatus.REJECTED):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending or rejected jobs can be deleted.")
        self.repository.delete(job)

    def close_job(self, user: User, job_id: uuid.UUID) -> Job:
        job = self.get_job(user, job_id)
        if job.status != JobStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only approved jobs can be closed.")
        job.status = JobStatus.CLOSED
        return self.repository.save(job)
