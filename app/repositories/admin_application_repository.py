import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV
from app.models.job import Job
from app.models.user import User


class AdminApplicationRepository:
    """Read-only persistence queries for application audit."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _audit_loads():
        return (
            joinedload(JobApplication.candidate),
            joinedload(JobApplication.job),
            joinedload(JobApplication.cv).joinedload(CV.template),
        )

    def list_applications(
        self,
        application_status: JobApplicationStatus | None,
        search: str | None,
        job_id: uuid.UUID | None,
        candidate_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[JobApplication], int]:
        query = self.db.query(JobApplication)
        if application_status is not None:
            query = query.filter(JobApplication.status == application_status)
        if job_id is not None:
            query = query.filter(JobApplication.job_id == job_id)
        if candidate_id is not None:
            query = query.filter(JobApplication.candidate_id == candidate_id)
        if search:
            search_pattern = f"%{search}%"
            query = query.join(JobApplication.candidate).join(JobApplication.job).filter(
                or_(
                    User.full_name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    Job.title.ilike(search_pattern),
                    Job.company_name.ilike(search_pattern),
                )
            )

        total = query.count()
        items = (
            query.options(*self._audit_loads())
            # Admin audit should surface the most recently changed application first.
            # New submissions are covered too because updated_at is initialized at creation.
            .order_by(JobApplication.updated_at.desc(), JobApplication.created_at.desc(), JobApplication.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, application_id: uuid.UUID) -> JobApplication | None:
        return (
            self.db.query(JobApplication)
            .options(*self._audit_loads())
            .filter(JobApplication.id == application_id)
            .first()
        )
