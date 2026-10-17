import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.admin_user_repository import AdminUserRepository
from app.repositories.admin_audit_log_repository import AdminAuditLogRepository
from app.schemas.admin_user import (
    AdminAdministratorOverview,
    AdminCandidateOverview,
    AdminRecruiterCompanyOverview,
    AdminRecruiterOverview,
    AdminRecruiterPlanOverview,
    AdminUserRecentApplication,
    AdminUserRecentAuditAction,
    AdminUserRecentCV,
    AdminUserRecentJob,
    AdminUserRecentPaymentOrder,
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserRoleOverviewResponse,
)
from app.services.subscription_service import SubscriptionService
from app.models.payment import PaymentOrderStatus
from datetime import datetime, timezone


class AdminUserService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminUserRepository(db)
        self.audit_repository = AdminAuditLogRepository(db)

    def list_users(
        self,
        role: UserRole | None,
        is_active: bool | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> AdminUserListResponse:
        normalized_search = search.strip() if search else None
        items, total = self.repository.list_users(role, is_active, normalized_search, page, page_size)
        return AdminUserListResponse(
            items=[AdminUserListItem.model_validate(user) for user in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_user(self, user_id: uuid.UUID) -> AdminUserDetailResponse:
        return AdminUserDetailResponse.model_validate(self._get_user_or_404(user_id))

    def get_user_overview(self, user_id: uuid.UUID) -> AdminUserRoleOverviewResponse:
        user = self._get_user_or_404(user_id)
        if user.role == UserRole.CANDIDATE:
            data = self.repository.candidate_overview(user.id)
            return AdminUserRoleOverviewResponse(
                user_id=user.id,
                role=user.role,
                candidate=AdminCandidateOverview(
                    **{key: data[key] for key in (
                        "cv_total", "analyzed_cv_total", "uploaded_cv_total",
                        "application_total", "hired_total", "saved_job_total",
                    )},
                    recent_cvs=[AdminUserRecentCV.model_validate(item, from_attributes=True) for item in data["recent_cvs"]],
                    recent_applications=[
                        AdminUserRecentApplication(
                            id=application.id,
                            job_id=job.id,
                            job_title=job.title,
                            company_name=job.company_name,
                            status=application.status,
                            updated_at=application.updated_at,
                        )
                        for application, job in data["recent_applications"]
                    ],
                ),
            )
        if user.role == UserRole.RECRUITER:
            data = self.repository.recruiter_overview(user.id)
            effective = SubscriptionService(self.repository.db).get_for_admin(user.id)
            return AdminUserRoleOverviewResponse(
                user_id=user.id,
                role=user.role,
                recruiter=AdminRecruiterOverview(
                    company_profile=(
                        AdminRecruiterCompanyOverview.model_validate(
                            data["company_profile"], from_attributes=True
                        )
                        if data["company_profile"] is not None
                        else None
                    ),
                    current_plan=AdminRecruiterPlanOverview(
                        code=effective.effective_plan.code,
                        name=effective.effective_plan.name,
                        source=effective.subscription.source if effective.subscription else None,
                        expires_at=effective.subscription.expires_at if effective.subscription else None,
                    ),
                    **{key: data[key] for key in (
                        "job_total", "pending_job_total", "approved_job_total",
                        "closed_job_total", "received_application_total", "paid_order_total",
                        "successful_payment_total", "revenue",
                    )},
                    recent_jobs=[
                        AdminUserRecentJob(
                            id=job.id,
                            title=job.title,
                            status=job.status,
                            application_total=application_total,
                            updated_at=job.updated_at,
                        )
                        for job, application_total in data["recent_jobs"]
                    ],
                    recent_payment_orders=[
                        AdminUserRecentPaymentOrder(
                            id=order.id,
                            payment_code=order.payment_code,
                            plan_name=order.plan_name_snapshot,
                            amount=order.amount,
                            currency=order.currency,
                            status=self._effective_payment_status(order.status, order.expires_at),
                            created_at=order.created_at,
                        )
                        for order in data["recent_payment_orders"]
                    ],
                ),
            )
        data = self.repository.administrator_overview(user.id)
        return AdminUserRoleOverviewResponse(
            user_id=user.id,
            role=user.role,
            administrator=AdminAdministratorOverview(
                audit_action_total=data["audit_action_total"],
                recent_actions=[
                    AdminUserRecentAuditAction.model_validate(item, from_attributes=True)
                    for item in data["recent_actions"]
                ],
            ),
        )

    @staticmethod
    def _effective_payment_status(
        current_status: PaymentOrderStatus, expires_at: datetime
    ) -> PaymentOrderStatus:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if current_status == PaymentOrderStatus.PENDING and expires_at <= datetime.now(timezone.utc):
            return PaymentOrderStatus.EXPIRED
        return PaymentOrderStatus(current_status)

    def activate_user(self, user_id: uuid.UUID, current_user: User) -> AdminUserDetailResponse:
        updated_user = self._transition_active_status(
            user_id=user_id,
            current_user=current_user,
            expected_current_status=False,
            target_status=True,
            action="USER_ACTIVATED",
        )
        if updated_user is not None:
            return AdminUserDetailResponse.model_validate(updated_user)

        self._get_user_or_404(user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already active.",
        )

    def deactivate_user(self, user_id: uuid.UUID, current_user: User) -> AdminUserDetailResponse:
        user = self._get_user_or_404(user_id)
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bạn không thể vô hiệu hóa tài khoản của chính mình.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account is already inactive.",
            )
        if user.role == UserRole.ADMIN and self.repository.count_active_admins() <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active admin account cannot be deactivated.",
            )

        updated_user = self._transition_active_status(
            user_id=user_id,
            current_user=current_user,
            expected_current_status=True,
            target_status=False,
            action="USER_DEACTIVATED",
        )
        if updated_user is not None:
            return AdminUserDetailResponse.model_validate(updated_user)

        self._get_user_or_404(user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already inactive.",
        )

    def _get_user_or_404(self, user_id: uuid.UUID) -> User:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    def _transition_active_status(
        self,
        *,
        user_id: uuid.UUID,
        current_user: User,
        expected_current_status: bool,
        target_status: bool,
        action: str,
    ) -> User | None:
        try:
            updated_user = self.repository.transition_active_status(
                user_id,
                expected_current_status=expected_current_status,
                target_status=target_status,
            )
            if updated_user is None:
                return None
            self.audit_repository.add(
                admin_user_id=current_user.id,
                action=action,
                entity_type="USER",
                entity_id=user_id,
                metadata={"from_active": expected_current_status, "to_active": target_status},
            )
            self.repository.commit()
            return updated_user
        except Exception:
            self.repository.rollback()
            raise
