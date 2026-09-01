import uuid

from sqlalchemy.orm import Session

from app.models.application import JobApplication


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_candidate_and_job(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> JobApplication | None:
        return self.db.query(JobApplication).filter(
            JobApplication.candidate_id == candidate_id,
            JobApplication.job_id == job_id,
        ).first()

    def add(self, application: JobApplication) -> None:
        self.db.add(application)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, application: JobApplication) -> JobApplication:
        self.db.refresh(application)
        return application
