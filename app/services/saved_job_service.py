import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.recruiter_profile import RecruiterProfile
from app.models.saved_job import SavedJob
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.repositories.saved_job_repository import SavedJobRepository
from app.schemas.saved_job import (
    SavedJobListItem,
    SavedJobListResponse,
    SavedJobStatusResponse,
    SavedJobSummary,
)


class SavedJobService:
    def __init__(self, db: Session) -> None:
        self.repository = SavedJobRepository(db)
        self.job_repository = JobRepository(db)

    @staticmethod
    def _status_response(saved_job: SavedJob | None) -> SavedJobStatusResponse:
        return SavedJobStatusResponse(
            saved=saved_job is not None,
            saved_at=saved_job.created_at if saved_job else None,
        )

    @staticmethod
    def _list_item(
        saved_job: SavedJob,
        job: Job,
        profile: RecruiterProfile | None,
    ) -> SavedJobListItem:
        return SavedJobListItem(
            id=saved_job.id,
            saved_at=saved_job.created_at,
            job=SavedJobSummary(
                id=job.id,
                title=job.title,
                company_name=profile.company_name if profile and profile.company_name else job.company_name,
                company_logo_url=profile.company_logo_url if profile else None,
                location=job.location,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_type=job.salary_type,
                salary_fixed=job.salary_fixed,
                salary_currency=job.salary_currency,
                employment_type=job.employment_type,
                experience_requirement=job.experience_requirement,
                work_mode=job.work_mode,
                industry=job.industry,
                status=job.status,
                created_at=job.created_at,
            ),
        )

    def save_job(self, current_user: User, job_id: uuid.UUID) -> SavedJobStatusResponse:
        job = self.job_repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        if job.status != JobStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only approved jobs can be saved.",
            )

        existing = self.repository.get(current_user.id, job_id)
        if existing is not None:
            return self._status_response(existing)

        saved_job = SavedJob(candidate_id=current_user.id, job_id=job_id)
        try:
            saved_job = self.repository.create(saved_job)
        except IntegrityError:
            self.repository.rollback()
            saved_job = self.repository.get(current_user.id, job_id)
            if saved_job is None:
                raise
        return self._status_response(saved_job)

    def unsave_job(self, current_user: User, job_id: uuid.UUID) -> None:
        self.repository.delete(current_user.id, job_id)

    def get_status(self, current_user: User, job_id: uuid.UUID) -> SavedJobStatusResponse:
        return self._status_response(self.repository.get(current_user.id, job_id))

    def list_saved_jobs(
        self,
        current_user: User,
        page: int,
        page_size: int,
    ) -> SavedJobListResponse:
        rows, total = self.repository.list_for_candidate(current_user.id, page, page_size)
        return SavedJobListResponse(
            items=[self._list_item(*row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )
