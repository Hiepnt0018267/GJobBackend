import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.recruiter_profile import RecruiterProfile
from app.models.user import User
from app.repositories.admin_job_repository import AdminJobRepository
from app.repositories.admin_audit_log_repository import AdminAuditLogRepository
from app.schemas.admin_job import AdminJobListResponse, AdminJobResponse
from app.schemas.job import JobResponse


class AdminJobService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminJobRepository(db)
        self.audit_repository = AdminAuditLogRepository(db)

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
            items=self._to_responses(items),
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_job(self, job_id: uuid.UUID) -> AdminJobResponse:
        return self._to_response(self._get_job_or_404(job_id))

    def approve_job(self, job_id: uuid.UUID, current_user: User) -> AdminJobResponse:
        return self._to_response(
            self._transition_pending_job(
                job_id,
                JobStatus.APPROVED,
                "Only pending jobs can be approved.",
                current_user,
            )
        )

    def reject_job(self, job_id: uuid.UUID, current_user: User) -> AdminJobResponse:
        return self._to_response(
            self._transition_pending_job(
                job_id,
                JobStatus.REJECTED,
                "Only pending jobs can be rejected.",
                current_user,
            )
        )

    def _get_job_or_404(self, job_id: uuid.UUID) -> Job:
        job = self.repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    def _to_responses(self, jobs: list[Job]) -> list[AdminJobResponse]:
        recruiter_ids = {job.recruiter_id for job in jobs if job.recruiter_id is not None}
        contexts = self.repository.get_recruiter_contexts(recruiter_ids)
        return [self._to_response(job, contexts.get(job.recruiter_id)) for job in jobs]

    def _to_response(
        self,
        job: Job,
        context: tuple[User, RecruiterProfile | None] | None = None,
    ) -> AdminJobResponse:
        if context is None and job.recruiter_id is not None:
            context = self.repository.get_recruiter_contexts({job.recruiter_id}).get(job.recruiter_id)
        recruiter, company_profile = context if context is not None else (None, None)
        payload = JobResponse.model_validate(job).model_dump()
        return AdminJobResponse(
            **payload,
            recruiter_id=job.recruiter_id,
            recruiter_account=recruiter,
            company_profile=company_profile,
        )

    def _transition_pending_job(
        self,
        job_id: uuid.UUID,
        target_status: JobStatus,
        conflict_detail: str,
        current_user: User,
    ) -> Job:
        try:
            job = self.repository.transition_pending_job(job_id, target_status)
            if job is not None:
                self.audit_repository.add(
                    admin_user_id=current_user.id,
                    action=f"JOB_{target_status.value}",
                    entity_type="JOB",
                    entity_id=job.id,
                    metadata={"from_status": JobStatus.PENDING.value, "to_status": target_status.value},
                )
                self.repository.commit()
                return job
        except Exception:
            self.repository.rollback()
            raise

        self._get_job_or_404(job_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail)
