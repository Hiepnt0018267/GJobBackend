from sqlalchemy.orm import Session

from app.models.application import JobApplicationStatus
from app.models.job import JobStatus
from app.models.user import UserRole
from app.repositories.admin_dashboard_repository import AdminDashboardRepository
from app.schemas.admin_dashboard import (
    AdminApplicationStats,
    AdminCVStats,
    AdminCVTemplateStats,
    AdminDashboardResponse,
    AdminJobStats,
    AdminUserStats,
)


class AdminDashboardService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminDashboardRepository(db)

    def get_dashboard_stats(self) -> AdminDashboardResponse:
        user_total, active_users, inactive_users = self.repository.get_user_total_and_activity_counts()
        users_by_role = self.repository.get_user_counts_by_role()
        job_total, jobs_by_status = self.repository.get_job_total_and_counts_by_status()
        application_total, applications_by_status = self.repository.get_application_total_and_counts_by_status()
        template_total, active_templates, inactive_templates = self.repository.get_cv_template_total_and_activity_counts()

        return AdminDashboardResponse(
            users=AdminUserStats(
                total=user_total,
                candidates=users_by_role.get(UserRole.CANDIDATE, 0),
                recruiters=users_by_role.get(UserRole.RECRUITER, 0),
                admins=users_by_role.get(UserRole.ADMIN, 0),
                active=active_users,
                inactive=inactive_users,
            ),
            jobs=AdminJobStats(
                total=job_total,
                pending=jobs_by_status.get(JobStatus.PENDING, 0),
                approved=jobs_by_status.get(JobStatus.APPROVED, 0),
                rejected=jobs_by_status.get(JobStatus.REJECTED, 0),
                closed=jobs_by_status.get(JobStatus.CLOSED, 0),
            ),
            applications=AdminApplicationStats(
                total=application_total,
                submitted=applications_by_status.get(JobApplicationStatus.SUBMITTED, 0),
                reviewing=applications_by_status.get(JobApplicationStatus.REVIEWING, 0),
                shortlisted=applications_by_status.get(JobApplicationStatus.SHORTLISTED, 0),
                rejected=applications_by_status.get(JobApplicationStatus.REJECTED, 0),
                hired=applications_by_status.get(JobApplicationStatus.HIRED, 0),
                withdrawn=applications_by_status.get(JobApplicationStatus.WITHDRAWN, 0),
            ),
            cvs=AdminCVStats(total=self.repository.get_cv_total()),
            cv_templates=AdminCVTemplateStats(total=template_total, active=active_templates, inactive=inactive_templates),
        )
