import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.recruiter_profile import RecruiterProfile


class RecruiterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[RecruiterProfile]:
        return self.db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user_id).first()

    def create(self, profile: RecruiterProfile) -> RecruiterProfile:
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def update(self, profile: RecruiterProfile, fields: dict) -> RecruiterProfile:
        for key, value in fields.items():
            setattr(profile, key, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def job_counts(self, user_id: uuid.UUID) -> dict[JobStatus, int]:
        rows = self.db.query(Job.status, func.count(Job.id)).filter(Job.recruiter_id == user_id).group_by(Job.status).all()
        return {status: count for status, count in rows}
