import uuid

from sqlalchemy.orm import Session

from app.models.application import JobApplication
from app.models.application_status_history import ApplicationStatusHistory


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

    def flush(self) -> None:
        self.db.flush()

    def add_status_history(
        self,
        application: JobApplication,
        changed_by_user_id: uuid.UUID,
    ) -> None:
        self.db.add(
            ApplicationStatusHistory(
                application_id=application.id,
                from_status=None,
                to_status=application.status,
                changed_by_user_id=changed_by_user_id,
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, application: JobApplication) -> JobApplication:
        self.db.refresh(application)
        return application
