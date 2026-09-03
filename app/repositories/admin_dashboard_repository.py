from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV
from app.models.cv_template import CVTemplate
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole


class AdminDashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_total_and_activity_counts(self) -> tuple[int, int, int]:
        total, active, inactive = self.db.query(
            func.count(User.id),
            func.count(User.id).filter(User.is_active.is_(True)),
            func.count(User.id).filter(User.is_active.is_(False)),
        ).one()
        return total, active, inactive

    def get_user_counts_by_role(self) -> dict[UserRole, int]:
        return {role: count for role, count in self.db.query(User.role, func.count(User.id)).group_by(User.role).all()}

    def get_job_total_and_counts_by_status(self) -> tuple[int, dict[JobStatus, int]]:
        total = self.db.query(func.count(Job.id)).scalar()
        counts = {job_status: count for job_status, count in self.db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()}
        return total, counts

    def get_application_total_and_counts_by_status(self) -> tuple[int, dict[JobApplicationStatus, int]]:
        total = self.db.query(func.count(JobApplication.id)).scalar()
        counts = {application_status: count for application_status, count in self.db.query(JobApplication.status, func.count(JobApplication.id)).group_by(JobApplication.status).all()}
        return total, counts

    def get_cv_total(self) -> int:
        return self.db.query(func.count(CV.id)).scalar()

    def get_cv_template_total_and_activity_counts(self) -> tuple[int, int, int]:
        total, active, inactive = self.db.query(
            func.count(CVTemplate.id),
            func.count(CVTemplate.id).filter(CVTemplate.is_active.is_(True)),
            func.count(CVTemplate.id).filter(CVTemplate.is_active.is_(False)),
        ).filter(CVTemplate.is_deleted.is_(False)).one()
        return total, active, inactive
