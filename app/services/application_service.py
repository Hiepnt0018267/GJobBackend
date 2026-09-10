import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.application import JobApplication, JobApplicationStatus
from app.models.job import JobStatus
from app.models.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.job_repository import JobRepository
from app.schemas.application import JobApplicationCreate


class ApplicationService:
    def __init__(self, db: Session) -> None:
        self.application_repository = ApplicationRepository(db)
        self.cv_repository = CVRepository(db)
        self.job_repository = JobRepository(db)

    def submit_application(self, user: User, job_id: uuid.UUID, payload: JobApplicationCreate) -> JobApplication:
        job = self.job_repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        if job.status != JobStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This job is not accepting applications.")

        cv = self.cv_repository.get_for_candidate(payload.cv_id, user.id)
        if cv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
        if self.application_repository.get_by_candidate_and_job(user.id, job_id) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already applied for this job.")

        application = JobApplication(
            job_id=job.id,
            candidate_id=user.id,
            cv_id=cv.id,
            status=JobApplicationStatus.SUBMITTED,
        )
        self.application_repository.add(application)
        try:
            self.application_repository.flush()
            self.application_repository.add_status_history(application, user.id)
            self.application_repository.commit()
        except IntegrityError as exc:
            self.application_repository.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already applied for this job.") from exc
        except Exception:
            self.application_repository.rollback()
            raise
        return self.application_repository.refresh(application)
