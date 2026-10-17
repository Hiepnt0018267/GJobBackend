import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.recruiter_profile import RecruiterProfile
from app.models.user import User


class AdminJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_jobs(
        self,
        job_status: JobStatus | None,
        search: str | None,
        recruiter_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Job], int]:
        query = self.db.query(Job)
        if job_status is not None:
            query = query.filter(Job.status == job_status)
        if recruiter_id is not None:
            query = query.filter(Job.recruiter_id == recruiter_id)
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Job.title.ilike(search_pattern),
                    Job.company_name.ilike(search_pattern),
                )
            )
        total = query.count()
        items = query.order_by(Job.created_at.desc(), Job.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        return self.db.query(Job).filter(Job.id == job_id).first()

    def get_recruiter_contexts(
        self,
        recruiter_ids: set[uuid.UUID],
    ) -> dict[uuid.UUID, tuple[User, RecruiterProfile | None]]:
        if not recruiter_ids:
            return {}
        rows = (
            self.db.query(User, RecruiterProfile)
            .outerjoin(RecruiterProfile, RecruiterProfile.user_id == User.id)
            .filter(User.id.in_(recruiter_ids))
            .all()
        )
        return {user.id: (user, profile) for user, profile in rows}

    def transition_pending_job(self, job_id: uuid.UUID, target_status: JobStatus) -> Job | None:
        affected_rows = (
            self.db.query(Job)
            .filter(Job.id == job_id, Job.status == JobStatus.PENDING)
            .update(
                {Job.status: target_status, Job.updated_at: func.now()},
                synchronize_session=False,
            )
        )
        if affected_rows == 0:
            return None
        return self.get_by_id(job_id)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
