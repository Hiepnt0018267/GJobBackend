import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.subscription import (
    RecruiterSubscription,
    SubscriptionPlan,
    SubscriptionSource,
    SubscriptionStatus,
)
from app.models.user import User, UserRole
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import (
    AdminRecruiterSubscriptionItem,
    AdminRecruiterSubscriptionListResponse,
    CurrentSubscriptionResponse,
    EffectivePlanResponse,
    EffectiveSubscriptionResponse,
    SubscriptionGrantRequest,
    SubscriptionPlanCreateRequest,
    SubscriptionPlanListResponse,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdateRequest,
    validate_plan_semantics,
)


class PaymentPlanConflictError(RuntimeError):
    """Raised when a paid order cannot safely mutate the current paid plan."""


class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SubscriptionRepository(db)

    def list_plans(
        self, *, is_active: bool | None, page: int, page_size: int
    ) -> SubscriptionPlanListResponse:
        items, total = self.repository.list_plans(
            is_active=is_active, page=page, page_size=page_size
        )
        return SubscriptionPlanListResponse(
            items=[SubscriptionPlanResponse.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_plan(self, plan_id: uuid.UUID) -> SubscriptionPlanResponse:
        return SubscriptionPlanResponse.model_validate(self._get_plan_or_404(plan_id))

    def create_plan(self, payload: SubscriptionPlanCreateRequest) -> SubscriptionPlanResponse:
        plan = SubscriptionPlan(**payload.model_dump())
        try:
            self.repository.add_plan(plan)
            self.repository.commit()
            self.repository.refresh(plan)
        except IntegrityError as exc:
            self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A subscription plan with this code already exists.",
            ) from exc
        return SubscriptionPlanResponse.model_validate(plan)

    def update_plan(
        self, plan_id: uuid.UUID, payload: SubscriptionPlanUpdateRequest
    ) -> SubscriptionPlanResponse:
        values = payload.model_dump(exclude_unset=True)
        if not values:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one editable field.",
            )
        try:
            plan = self.repository.get_plan(plan_id, for_update=True)
            if plan is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")

            immutable_after_use = {"currency", "billing_period", "duration_days"}
            changed_immutable = {
                field for field in immutable_after_use if field in values and values[field] != getattr(plan, field)
            }
            if changed_immutable and self.repository.plan_has_history(plan.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Used plans cannot change currency, billing_period, or duration_days; "
                        "create a new plan code instead."
                    ),
                )

            validate_plan_semantics(
                code=plan.code,
                price=values.get("price", plan.price),
                currency=values.get("currency", plan.currency),
                billing_period=values.get("billing_period", plan.billing_period),
                duration_days=values.get("duration_days", plan.duration_days),
            )
            for field, value in values.items():
                setattr(plan, field, value)
            plan.updated_at = datetime.now(timezone.utc)
            self.repository.commit()
            self.repository.refresh(plan)
            return SubscriptionPlanResponse.model_validate(plan)
        except HTTPException:
            self.repository.rollback()
            raise
        except ValueError as exc:
            self.repository.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        except Exception:
            self.repository.rollback()
            raise

    def get_for_admin(self, recruiter_id: uuid.UUID) -> EffectiveSubscriptionResponse:
        self._require_recruiter(recruiter_id)
        return self._effective_response(recruiter_id, datetime.now(timezone.utc))

    def get_for_recruiter(self, recruiter: User) -> EffectiveSubscriptionResponse:
        return self._effective_response(recruiter.id, datetime.now(timezone.utc))

    def grant_or_change(
        self, recruiter_id: uuid.UUID, payload: SubscriptionGrantRequest
    ) -> EffectiveSubscriptionResponse:
        now = datetime.now(timezone.utc)
        starts_at = payload.starts_at or now
        try:
            self._require_recruiter(recruiter_id, for_update=True)
            plan = self.repository.get_plan(payload.plan_id, for_update=True)
            if plan is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")
            if plan.code == "FREE":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="FREE is an implicit fallback and cannot be granted.",
                )
            if not plan.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Inactive subscription plans cannot be granted.",
                )

            expires_at = payload.expires_at
            if expires_at is None and plan.duration_days is not None:
                expires_at = starts_at + timedelta(days=plan.duration_days)
            if expires_at is not None and expires_at <= starts_at:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="expires_at must be later than starts_at.",
                )

            self.apply_grant_or_change_no_commit(
                recruiter_id=recruiter_id,
                plan=plan,
                starts_at=starts_at,
                expires_at=expires_at,
                source=SubscriptionSource.ADMIN,
                now=now,
            )
            self.repository.commit()
        except HTTPException:
            self.repository.rollback()
            raise
        except IntegrityError as exc:
            self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The recruiter already has an active paid subscription.",
            ) from exc
        except Exception:
            self.repository.rollback()
            raise
        return self._effective_response(recruiter_id, now)

    def apply_grant_or_change_no_commit(
        self,
        *,
        recruiter_id: uuid.UUID,
        plan: SubscriptionPlan,
        starts_at: datetime,
        expires_at: datetime | None,
        source: SubscriptionSource,
        now: datetime,
    ) -> RecruiterSubscription:
        """Mutate subscription state without owning commit/rollback."""
        self._require_recruiter(recruiter_id, for_update=True)
        for subscription in self.repository.active_subscriptions_for_update(recruiter_id):
            if subscription.expires_at is not None and subscription.expires_at <= now:
                subscription.status = SubscriptionStatus.EXPIRED
            else:
                subscription.status = SubscriptionStatus.CANCELLED
            subscription.updated_at = now

        new_subscription = RecruiterSubscription(
            recruiter_id=recruiter_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=starts_at,
            expires_at=expires_at,
            source=source,
        )
        self.repository.add_subscription(new_subscription)
        self.repository.flush()
        return new_subscription

    def apply_payment_no_commit(
        self,
        *,
        recruiter_id: uuid.UUID,
        plan_id: uuid.UUID,
        duration_days: int,
        now: datetime,
    ) -> RecruiterSubscription:
        """Activate or renew a paid plan as part of the caller-owned transaction."""
        if duration_days <= 0:
            raise ValueError("Paid subscription duration must be positive.")
        self._require_recruiter(recruiter_id, for_update=True)
        plan = self.repository.get_plan(plan_id, for_update=True)
        if plan is None:
            raise PaymentPlanConflictError("The purchased plan no longer exists.")

        active_rows = self.repository.active_subscriptions_for_update(recruiter_id)
        effective: RecruiterSubscription | None = None
        for subscription in active_rows:
            if subscription.expires_at is not None and subscription.expires_at <= now:
                subscription.status = SubscriptionStatus.EXPIRED
                subscription.updated_at = now
            elif subscription.starts_at <= now:
                effective = subscription

        if effective is not None:
            if effective.plan_id != plan_id:
                raise PaymentPlanConflictError(
                    "A different paid subscription is already active."
                )
            if effective.expires_at is None:
                raise PaymentPlanConflictError(
                    "A perpetual subscription cannot be extended by this payment flow."
                )
            effective.expires_at = max(effective.expires_at, now) + timedelta(days=duration_days)
            effective.source = SubscriptionSource.PAYMENT
            effective.updated_at = now
            self.repository.flush()
            return effective

        created = RecruiterSubscription(
            recruiter_id=recruiter_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=now,
            expires_at=now + timedelta(days=duration_days),
            source=SubscriptionSource.PAYMENT,
        )
        self.repository.add_subscription(created)
        self.repository.flush()
        return created

    def revoke(self, recruiter_id: uuid.UUID) -> EffectiveSubscriptionResponse:
        now = datetime.now(timezone.utc)
        try:
            self._require_recruiter(recruiter_id, for_update=True)
            for subscription in self.repository.active_subscriptions_for_update(recruiter_id):
                if subscription.expires_at is not None and subscription.expires_at <= now:
                    subscription.status = SubscriptionStatus.EXPIRED
                else:
                    subscription.status = SubscriptionStatus.CANCELLED
                subscription.updated_at = now
            self.repository.commit()
        except HTTPException:
            self.repository.rollback()
            raise
        except Exception:
            self.repository.rollback()
            raise
        return self._effective_response(recruiter_id, now)

    def list_recruiters(
        self, *, page: int, page_size: int
    ) -> AdminRecruiterSubscriptionListResponse:
        now = datetime.now(timezone.utc)
        rows, total = self.repository.list_recruiters_with_effective_subscription(
            page=page, page_size=page_size, now=now
        )
        free_plan = self._free_plan()
        items = []
        for recruiter, paid_plan, subscription in rows:
            effective_plan = paid_plan or free_plan
            items.append(
                AdminRecruiterSubscriptionItem(
                    id=recruiter.id,
                    email=recruiter.email,
                    full_name=recruiter.full_name,
                    is_active=recruiter.is_active,
                    effective_plan=EffectivePlanResponse.model_validate(effective_plan),
                    subscription=(
                        CurrentSubscriptionResponse.model_validate(subscription)
                        if subscription is not None
                        else None
                    ),
                )
            )
        return AdminRecruiterSubscriptionListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def _get_plan_or_404(self, plan_id: uuid.UUID) -> SubscriptionPlan:
        plan = self.repository.get_plan(plan_id)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")
        return plan

    def _require_recruiter(self, user_id: uuid.UUID, *, for_update: bool = False) -> User:
        if for_update:
            user = self.repository.get_user_for_update(user_id)
        else:
            user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found.")
        if user.role != UserRole.RECRUITER:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Subscriptions can only be assigned to Recruiter accounts.",
            )
        return user

    def _free_plan(self) -> SubscriptionPlan:
        plan = self.repository.get_plan_by_code("FREE")
        if plan is None:
            raise RuntimeError("The required FREE subscription plan is missing.")
        return plan

    def _effective_response(
        self, recruiter_id: uuid.UUID, now: datetime
    ) -> EffectiveSubscriptionResponse:
        effective = self.repository.get_effective_subscription(recruiter_id, now)
        if effective is None:
            return EffectiveSubscriptionResponse(
                effective_plan=EffectivePlanResponse.model_validate(self._free_plan()),
                subscription=None,
            )
        subscription, plan = effective
        return EffectiveSubscriptionResponse(
            effective_plan=EffectivePlanResponse.model_validate(plan),
            subscription=CurrentSubscriptionResponse.model_validate(subscription),
        )
