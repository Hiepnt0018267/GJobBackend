import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.application import JobApplication, JobApplicationStatus
from app.models.application_status_history import ApplicationStatusHistory
from app.models.cv import CV
from app.models.job import Job
from app.models.user import User


class RecruiterApplicationRepository:
    """Persistence queries scoped to applications for jobs owned by one recruiter."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _relation_loads():
        return (
            joinedload(JobApplication.candidate),
            joinedload(JobApplication.job),
            joinedload(JobApplication.cv).joinedload(CV.template),
        )

    def list_owned_applications(
        self,
        recruiter_id: uuid.UUID,
        application_status: JobApplicationStatus | None,
        search: str | None,
        job_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[JobApplication], int]:
        query = (
            self.db.query(JobApplication)
            .join(JobApplication.job)
            .filter(Job.recruiter_id == recruiter_id)
        )

        if application_status is not None:
            query = query.filter(JobApplication.status == application_status)
        if job_id is not None:
            query = query.filter(JobApplication.job_id == job_id)
        if search:
            pattern = f"%{search}%"
            query = query.join(JobApplication.candidate).join(JobApplication.cv).filter(
                or_(
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                    Job.title.ilike(pattern),
                    CV.title.ilike(pattern),
                )
            )

        total = query.order_by(None).count()
        items = (
            query.options(*self._relation_loads())
            .order_by(JobApplication.created_at.desc(), JobApplication.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_owned_application(
        self, application_id: uuid.UUID, recruiter_id: uuid.UUID
    ) -> JobApplication | None:
        return (
            self.db.query(JobApplication)
            .join(JobApplication.job)
            .options(*self._relation_loads())
            .filter(
                JobApplication.id == application_id,
                Job.recruiter_id == recruiter_id,
            )
            .first()
        )

    def get_owned_job(self, job_id: uuid.UUID, recruiter_id: uuid.UUID) -> Job | None:
        return (
            self.db.query(Job)
            .filter(Job.id == job_id, Job.recruiter_id == recruiter_id)
            .first()
        )

    def transition_if_current(
        self,
        application_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        expected_status: JobApplicationStatus,
        next_status: JobApplicationStatus,
        changed_by_user_id: uuid.UUID | None = None,
    ) -> bool:
        owned_job_ids = select(Job.id).where(Job.recruiter_id == recruiter_id)
        result = self.db.execute(
            update(JobApplication)
            .where(
                JobApplication.id == application_id,
                JobApplication.job_id.in_(owned_job_ids),
                JobApplication.status == expected_status,
            )
            .values(status=next_status, updated_at=datetime.now(timezone.utc))
        )
        if result.rowcount == 1:
            self.db.add(
                ApplicationStatusHistory(
                    application_id=application_id,
                    from_status=expected_status,
                    to_status=next_status,
                    changed_by_user_id=changed_by_user_id,
                )
            )
        self.db.commit()
        self.db.expire_all()
        return result.rowcount == 1

    def rollback(self) -> None:
        self.db.rollback()
