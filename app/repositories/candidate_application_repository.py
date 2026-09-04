import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, update
from sqlalchemy.orm import Session, joinedload

from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV
from app.models.job import Job


class CandidateApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _relation_loads():
        return (
            joinedload(JobApplication.job),
            joinedload(JobApplication.cv).joinedload(CV.template),
        )

    def list_for_candidate(
        self,
        candidate_id: uuid.UUID,
        application_status: JobApplicationStatus | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[JobApplication], int]:
        query = self.db.query(JobApplication).filter(JobApplication.candidate_id == candidate_id)

        if application_status is not None:
            query = query.filter(JobApplication.status == application_status)

        if search:
            pattern = f"%{search}%"
            query = query.join(JobApplication.job).filter(
                or_(Job.title.ilike(pattern), Job.company_name.ilike(pattern))
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

    def get_owned(self, application_id: uuid.UUID, candidate_id: uuid.UUID) -> JobApplication | None:
        return (
            self.db.query(JobApplication)
            .options(*self._relation_loads())
            .filter(
                JobApplication.id == application_id,
                JobApplication.candidate_id == candidate_id,
            )
            .first()
        )

    def get_by_candidate_and_job(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID
    ) -> JobApplication | None:
        return (
            self.db.query(JobApplication)
            .filter(
                JobApplication.candidate_id == candidate_id,
                JobApplication.job_id == job_id,
            )
            .first()
        )

    def withdraw_if_eligible(
        self,
        application_id: uuid.UUID,
        candidate_id: uuid.UUID,
        expected_status: JobApplicationStatus,
    ) -> bool:
        result = self.db.execute(
            update(JobApplication)
            .where(
                JobApplication.id == application_id,
                JobApplication.candidate_id == candidate_id,
                JobApplication.status == expected_status,
            )
            .values(
                status=JobApplicationStatus.WITHDRAWN,
                updated_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        self.db.expire_all()
        return result.rowcount == 1

    def rollback(self) -> None:
        self.db.rollback()
