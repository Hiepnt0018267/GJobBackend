import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.repositories.admin_job_repository import AdminJobRepository
from app.schemas.admin_job import AdminJobListResponse, AdminJobResponse


class AdminJobService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminJobRepository(db)

    def list_jobs(
        self,
        job_status: JobStatus | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> AdminJobListResponse:
        normalized_search = search.strip() if search else None
        items, total = self.repository.list_jobs(job_status, normalized_search, page, page_size)
        return AdminJobListResponse(
            items=[AdminJobResponse.model_validate(job) for job in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_job(self, job_id: uuid.UUID) -> AdminJobResponse:
        return AdminJobResponse.model_validate(self._get_job_or_404(job_id))

    def approve_job(self, job_id: uuid.UUID) -> AdminJobResponse:
        return AdminJobResponse.model_validate(
            self._transition_pending_job(job_id, JobStatus.APPROVED, "Only pending jobs can be approved.")
        )

    def reject_job(self, job_id: uuid.UUID) -> AdminJobResponse:
        return AdminJobResponse.model_validate(
            self._transition_pending_job(job_id, JobStatus.REJECTED, "Only pending jobs can be rejected.")
        )

    def _get_job_or_404(self, job_id: uuid.UUID) -> Job:
        job = self.repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    def _transition_pending_job(self, job_id: uuid.UUID, target_status: JobStatus, conflict_detail: str) -> Job:
        job = self.repository.transition_pending_job(job_id, target_status)
        if job is not None:
            return job

        self._get_job_or_404(job_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail)
