import uuid

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.recruiter_profile import RecruiterProfile
from app.models.saved_job import SavedJob


class SavedJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> SavedJob | None:
        return (
            self.db.query(SavedJob)
            .filter(
                SavedJob.candidate_id == candidate_id,
                SavedJob.job_id == job_id,
            )
            .first()
        )

    def create(self, saved_job: SavedJob) -> SavedJob:
        self.db.add(saved_job)
        self.db.commit()
        self.db.refresh(saved_job)
        return saved_job

    def delete(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self.db.query(SavedJob).filter(
            SavedJob.candidate_id == candidate_id,
            SavedJob.job_id == job_id,
        ).delete(synchronize_session=False)
        self.db.commit()

    def list_for_candidate(
        self,
        candidate_id: uuid.UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[SavedJob, Job, RecruiterProfile | None]], int]:
        query = (
            self.db.query(SavedJob, Job, RecruiterProfile)
            .join(Job, Job.id == SavedJob.job_id)
            .outerjoin(
                RecruiterProfile,
                RecruiterProfile.user_id == Job.recruiter_id,
            )
            .filter(SavedJob.candidate_id == candidate_id)
        )
        total = query.order_by(None).count()
        items = (
            query.order_by(SavedJob.created_at.desc(), SavedJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def rollback(self) -> None:
        self.db.rollback()
