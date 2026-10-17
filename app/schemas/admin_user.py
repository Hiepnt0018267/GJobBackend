import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.user import UserRole
from app.models.application import JobApplicationStatus
from app.models.cv import CVSourceType
from app.models.job import JobStatus
from app.models.payment import PaymentOrderStatus
from app.models.subscription import SubscriptionSource


class AdminUserListItem(BaseModel):
    """Safe user fields used by the admin management list."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(AdminUserListItem):
    """Safe profile fields available to an administrator for support purposes."""

    phone: str | None
    address: str | None
    bio: str | None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class AdminUserRecentCV(BaseModel):
    id: uuid.UUID
    title: str
    source_type: CVSourceType
    is_default: bool
    updated_at: datetime


class AdminUserRecentApplication(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    status: JobApplicationStatus
    updated_at: datetime


class AdminCandidateOverview(BaseModel):
    cv_total: int
    analyzed_cv_total: int
    uploaded_cv_total: int
    application_total: int
    hired_total: int
    saved_job_total: int
    recent_cvs: list[AdminUserRecentCV]
    recent_applications: list[AdminUserRecentApplication]


class AdminRecruiterCompanyOverview(BaseModel):
    company_name: str | None
    company_website: str | None
    company_description: str | None
    company_address: str | None
    company_logo_url: str | None
    industry: str | None
    company_size: int | None

    model_config = {"from_attributes": True}


class AdminRecruiterPlanOverview(BaseModel):
    code: str
    name: str
    source: SubscriptionSource | None
    expires_at: datetime | None


class AdminUserRecentJob(BaseModel):
    id: uuid.UUID
    title: str
    status: JobStatus
    application_total: int
    updated_at: datetime


class AdminUserRecentPaymentOrder(BaseModel):
    id: uuid.UUID
    payment_code: str
    plan_name: str
    amount: Decimal
    currency: str
    status: PaymentOrderStatus
    created_at: datetime


class AdminRecruiterOverview(BaseModel):
    company_profile: AdminRecruiterCompanyOverview | None
    current_plan: AdminRecruiterPlanOverview
    job_total: int
    pending_job_total: int
    approved_job_total: int
    closed_job_total: int
    received_application_total: int
    paid_order_total: int
    successful_payment_total: int
    revenue: Decimal
    recent_jobs: list[AdminUserRecentJob]
    recent_payment_orders: list[AdminUserRecentPaymentOrder]


class AdminUserRecentAuditAction(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID
    created_at: datetime


class AdminAdministratorOverview(BaseModel):
    audit_action_total: int
    recent_actions: list[AdminUserRecentAuditAction]


class AdminUserRoleOverviewResponse(BaseModel):
    user_id: uuid.UUID
    role: UserRole
    candidate: AdminCandidateOverview | None = None
    recruiter: AdminRecruiterOverview | None = None
    administrator: AdminAdministratorOverview | None = None
