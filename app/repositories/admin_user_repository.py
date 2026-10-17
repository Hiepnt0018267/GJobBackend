import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.admin_audit_log import AdminAuditLog
from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV, CVSourceType
from app.models.cv_extraction import CVExtraction, CVExtractionStatus
from app.models.job import Job, JobStatus
from app.models.payment import PaymentDisposition, PaymentOrder, PaymentOrderStatus, PaymentTransaction
from app.models.recruiter_profile import RecruiterProfile
from app.models.saved_job import SavedJob
from app.models.user import User, UserRole


class AdminUserRepository:
    """Persistence operations for the admin-only user management module."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(
        self,
        role: UserRole | None,
        is_active: bool | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        query = self.db.query(User)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                )
            )
        if role is not None:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active.is_(is_active))

        total = query.count()
        items = (
            query.order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def count_active_admins(self) -> int:
        return (
            self.db.query(func.count(User.id))
            .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .scalar()
            or 0
        )

    def candidate_overview(self, user_id: uuid.UUID) -> dict[str, object]:
        cv_total = self.db.query(func.count(CV.id)).filter(CV.candidate_id == user_id).scalar() or 0
        uploaded_cv_total = (
            self.db.query(func.count(CV.id))
            .filter(CV.candidate_id == user_id, CV.source_type == CVSourceType.UPLOADED)
            .scalar()
            or 0
        )
        analyzed_cv_total = (
            self.db.query(func.count(func.distinct(CVExtraction.cv_id)))
            .join(CV, CV.id == CVExtraction.cv_id)
            .filter(
                CV.candidate_id == user_id,
                CVExtraction.status == CVExtractionStatus.SUCCEEDED,
            )
            .scalar()
            or 0
        )
        application_query = self.db.query(JobApplication).filter(
            JobApplication.candidate_id == user_id
        )
        recent_applications = (
            application_query.join(Job, Job.id == JobApplication.job_id)
            .with_entities(JobApplication, Job)
            .order_by(JobApplication.updated_at.desc(), JobApplication.id.desc())
            .limit(5)
            .all()
        )
        return {
            "cv_total": cv_total,
            "analyzed_cv_total": analyzed_cv_total,
            "uploaded_cv_total": uploaded_cv_total,
            "application_total": application_query.count(),
            "hired_total": application_query.filter(
                JobApplication.status == JobApplicationStatus.HIRED
            ).count(),
            "saved_job_total": self.db.query(func.count(SavedJob.id)).filter(
                SavedJob.candidate_id == user_id
            ).scalar()
            or 0,
            "recent_cvs": (
                self.db.query(CV)
                .filter(CV.candidate_id == user_id)
                .order_by(CV.updated_at.desc(), CV.id.desc())
                .limit(5)
                .all()
            ),
            "recent_applications": recent_applications,
        }

    def recruiter_overview(self, user_id: uuid.UUID) -> dict[str, object]:
        job_query = self.db.query(Job).filter(Job.recruiter_id == user_id)
        application_total = (
            self.db.query(func.count(JobApplication.id))
            .join(Job, Job.id == JobApplication.job_id)
            .filter(Job.recruiter_id == user_id)
            .scalar()
            or 0
        )
        paid_order_query = self.db.query(PaymentOrder).filter(
            PaymentOrder.recruiter_id == user_id,
            PaymentOrder.status == PaymentOrderStatus.PAID,
        )
        successful_payment_query = (
            self.db.query(PaymentTransaction)
            .join(PaymentOrder, PaymentOrder.id == PaymentTransaction.payment_order_id)
            .filter(
                PaymentOrder.recruiter_id == user_id,
                PaymentTransaction.disposition == PaymentDisposition.APPLIED,
            )
        )
        recent_jobs = (
            self.db.query(Job, func.count(JobApplication.id))
            .outerjoin(JobApplication, JobApplication.job_id == Job.id)
            .filter(Job.recruiter_id == user_id)
            .group_by(Job.id)
            .order_by(Job.updated_at.desc(), Job.id.desc())
            .limit(5)
            .all()
        )
        return {
            "company_profile": self.db.query(RecruiterProfile).filter(
                RecruiterProfile.user_id == user_id
            ).first(),
            "job_total": job_query.count(),
            "pending_job_total": job_query.filter(Job.status == JobStatus.PENDING).count(),
            "approved_job_total": job_query.filter(Job.status == JobStatus.APPROVED).count(),
            "closed_job_total": job_query.filter(Job.status == JobStatus.CLOSED).count(),
            "received_application_total": application_total,
            "paid_order_total": paid_order_query.count(),
            "successful_payment_total": successful_payment_query.count(),
            "revenue": successful_payment_query.with_entities(
                func.coalesce(func.sum(PaymentTransaction.amount), 0)
            ).scalar(),
            "recent_jobs": recent_jobs,
            "recent_payment_orders": (
                self.db.query(PaymentOrder)
                .filter(PaymentOrder.recruiter_id == user_id)
                .order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
                .limit(5)
                .all()
            ),
        }

    def administrator_overview(self, user_id: uuid.UUID) -> dict[str, object]:
        query = self.db.query(AdminAuditLog).filter(AdminAuditLog.admin_user_id == user_id)
        return {
            "audit_action_total": query.count(),
            "recent_actions": query.order_by(
                AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()
            ).limit(10).all(),
        }

    def transition_active_status(
        self,
        user_id: uuid.UUID,
        *,
        expected_current_status: bool,
        target_status: bool,
    ) -> User | None:
        """Atomically change a user status only when its current value is expected."""
        affected_rows = (
            self.db.query(User)
            .filter(User.id == user_id, User.is_active.is_(expected_current_status))
            .update(
                {User.is_active: target_status, User.updated_at: func.now()},
                synchronize_session=False,
            )
        )
        if affected_rows == 0:
            return None
        return self.get_by_id(user_id)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
