import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.subscription import RecruiterSubscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User, UserRole


class SubscriptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_plans(
        self, *, is_active: bool | None, page: int, page_size: int
    ) -> tuple[list[SubscriptionPlan], int]:
        query = self.db.query(SubscriptionPlan)
        if is_active is not None:
            query = query.filter(SubscriptionPlan.is_active.is_(is_active))
        total = query.count()
        items = (
            query.order_by(SubscriptionPlan.created_at.desc(), SubscriptionPlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_active_plans(self) -> list[SubscriptionPlan]:
        return (
            self.db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.price.asc(), SubscriptionPlan.created_at.asc())
            .all()
        )

    def list_active_plans(self) -> list[SubscriptionPlan]:
        return (
            self.db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.price.asc(), SubscriptionPlan.created_at.asc())
            .all()
        )

    def list_active_plans(self) -> list[SubscriptionPlan]:
        return (
            self.db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.price.asc(), SubscriptionPlan.created_at.asc())
            .all()
        )

    def get_plan(self, plan_id: uuid.UUID, *, for_update: bool = False) -> SubscriptionPlan | None:
        query = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    def get_plan_by_code(self, code: str) -> SubscriptionPlan | None:
        return self.db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()

    def add_plan(self, plan: SubscriptionPlan) -> None:
        self.db.add(plan)

    def plan_has_history(self, plan_id: uuid.UUID) -> bool:
        return (
            self.db.query(RecruiterSubscription.id)
            .filter(RecruiterSubscription.plan_id == plan_id)
            .first()
            is not None
        )

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).with_for_update().first()

    def active_subscriptions_for_update(self, recruiter_id: uuid.UUID) -> list[RecruiterSubscription]:
        return (
            self.db.query(RecruiterSubscription)
            .filter(
                RecruiterSubscription.recruiter_id == recruiter_id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(RecruiterSubscription.created_at, RecruiterSubscription.id)
            .with_for_update()
            .all()
        )

    def add_subscription(self, subscription: RecruiterSubscription) -> None:
        self.db.add(subscription)

    def get_effective_subscription(
        self, recruiter_id: uuid.UUID, now: datetime
    ) -> tuple[RecruiterSubscription, SubscriptionPlan] | None:
        return (
            self.db.query(RecruiterSubscription, SubscriptionPlan)
            .join(SubscriptionPlan, SubscriptionPlan.id == RecruiterSubscription.plan_id)
            .filter(
                RecruiterSubscription.recruiter_id == recruiter_id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
                RecruiterSubscription.starts_at <= now,
                or_(
                    RecruiterSubscription.expires_at.is_(None),
                    RecruiterSubscription.expires_at > now,
                ),
            )
            .first()
        )

    def list_recruiters_with_effective_subscription(
        self, *, page: int, page_size: int, now: datetime
    ) -> tuple[list[tuple[User, SubscriptionPlan | None, RecruiterSubscription | None]], int]:
        effective_join = and_(
            RecruiterSubscription.recruiter_id == User.id,
            RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            RecruiterSubscription.starts_at <= now,
            or_(
                RecruiterSubscription.expires_at.is_(None),
                RecruiterSubscription.expires_at > now,
            ),
        )
        query = (
            self.db.query(User, SubscriptionPlan, RecruiterSubscription)
            .outerjoin(RecruiterSubscription, effective_join)
            .outerjoin(SubscriptionPlan, SubscriptionPlan.id == RecruiterSubscription.plan_id)
            .filter(User.role == UserRole.RECRUITER)
        )
        total = self.db.query(func.count(User.id)).filter(User.role == UserRole.RECRUITER).scalar() or 0
        rows = (
            query.order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return rows, total

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)
