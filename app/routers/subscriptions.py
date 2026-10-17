import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.subscription import (
    AdminRecruiterSubscriptionListResponse,
    EffectiveSubscriptionResponse,
    RecruiterEffectiveSubscriptionResponse,
    RecruiterPlanCatalogItem,
    SubscriptionGrantRequest,
    SubscriptionPlanCreateRequest,
    SubscriptionPlanListResponse,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdateRequest,
)
from app.services.recruiter_entitlement_service import RecruiterEntitlementService
from app.services.subscription_service import SubscriptionService


router = APIRouter(tags=["Subscriptions"])


@router.get("/admin/subscription-plans", response_model=SubscriptionPlanListResponse)
def list_subscription_plans(
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).list_plans(is_active=is_active, page=page, page_size=page_size)


@router.get("/admin/subscription-plans/{plan_id}", response_model=SubscriptionPlanResponse)
def get_subscription_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).get_plan(plan_id)


@router.post(
    "/admin/subscription-plans",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription_plan(
    payload: SubscriptionPlanCreateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).create_plan(payload)


@router.patch("/admin/subscription-plans/{plan_id}", response_model=SubscriptionPlanResponse)
def update_subscription_plan(
    plan_id: uuid.UUID,
    payload: SubscriptionPlanUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).update_plan(plan_id, payload)


@router.get("/admin/recruiters", response_model=AdminRecruiterSubscriptionListResponse)
def list_recruiters_for_subscription_management(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).list_recruiters(page=page, page_size=page_size)


@router.get(
    "/admin/recruiters/{recruiter_id}/subscription",
    response_model=EffectiveSubscriptionResponse,
)
def get_recruiter_subscription(
    recruiter_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).get_for_admin(recruiter_id)


@router.post(
    "/admin/recruiters/{recruiter_id}/subscription",
    response_model=EffectiveSubscriptionResponse,
)
def grant_or_change_recruiter_subscription(
    recruiter_id: uuid.UUID,
    payload: SubscriptionGrantRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).grant_or_change(recruiter_id, payload)


@router.post(
    "/admin/recruiters/{recruiter_id}/subscription/revoke",
    response_model=EffectiveSubscriptionResponse,
)
def revoke_recruiter_subscription(
    recruiter_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return SubscriptionService(db).revoke(recruiter_id)


@router.get(
    "/recruiter/subscription-plans",
    response_model=list[RecruiterPlanCatalogItem],
)
def list_recruiter_subscription_plans(
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return RecruiterEntitlementService(db).list_active_plan_catalog()


@router.get(
    "/recruiter/subscription",
    response_model=RecruiterEffectiveSubscriptionResponse,
)
def get_my_subscription(
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    subscription = SubscriptionService(db).get_for_recruiter(current_user)
    return RecruiterEffectiveSubscriptionResponse(
        **subscription.model_dump(),
        entitlements=RecruiterEntitlementService.for_plan_code(
            subscription.effective_plan.code
        ),
    )
