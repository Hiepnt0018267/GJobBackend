import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BillingPeriod(str, enum.Enum):
    NONE = "NONE"
    MONTHLY = "MONTHLY"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class SubscriptionSource(str, enum.Enum):
    ADMIN = "ADMIN"
    PAYMENT = "PAYMENT"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_subscription_plans_price_nonnegative"),
        CheckConstraint(
            "duration_days IS NULL OR duration_days > 0",
            name="ck_subscription_plans_duration_positive",
        ),
        CheckConstraint("currency = 'VND'", name="ck_subscription_plans_currency_vnd"),
        CheckConstraint(
            "code = upper(code) AND code ~ '^[A-Z][A-Z0-9_]*$'",
            name="ck_subscription_plans_code_format",
        ),
        CheckConstraint(
            "char_length(btrim(name)) > 0",
            name="ck_subscription_plans_name_not_blank",
        ),
        CheckConstraint(
            "billing_period IN ('NONE', 'MONTHLY')",
            name="ck_subscription_plans_billing_period",
        ),
        CheckConstraint(
            "(code = 'FREE' AND price = 0 AND billing_period = 'NONE' AND duration_days IS NULL) "
            "OR (code <> 'FREE' AND price > 0 AND billing_period = 'MONTHLY' AND duration_days > 0)",
            name="ck_subscription_plans_semantics",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="VND")
    billing_period: Mapped[BillingPeriod] = mapped_column(String(16), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    subscriptions: Mapped[list["RecruiterSubscription"]] = relationship(back_populates="plan")


class RecruiterSubscription(Base):
    __tablename__ = "recruiter_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED', 'EXPIRED')",
            name="ck_recruiter_subscriptions_status",
        ),
        CheckConstraint(
            "source IN ('ADMIN', 'PAYMENT')",
            name="ck_recruiter_subscriptions_source",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > starts_at",
            name="ck_recruiter_subscriptions_valid_interval",
        ),
        Index(
            "uq_recruiter_subscriptions_one_active",
            "recruiter_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "ix_recruiter_subscriptions_recruiter_created",
            "recruiter_id",
            "created_at",
        ),
        Index("ix_recruiter_subscriptions_plan_id", "plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(16), nullable=False, default=SubscriptionStatus.ACTIVE
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[SubscriptionSource] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    plan: Mapped[SubscriptionPlan] = relationship(back_populates="subscriptions")
