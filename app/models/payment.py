import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentOrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PaymentProvider(str, enum.Enum):
    SEPAY = "SEPAY"


class PaymentDisposition(str, enum.Enum):
    APPLIED = "APPLIED"
    UNMATCHED = "UNMATCHED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    ORDER_EXPIRED = "ORDER_EXPIRED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    OUTGOING_IGNORED = "OUTGOING_IGNORED"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_orders_amount_positive"),
        CheckConstraint("currency = 'VND'", name="ck_payment_orders_currency_vnd"),
        CheckConstraint("duration_days_snapshot > 0", name="ck_payment_orders_duration_positive"),
        CheckConstraint(
            "billing_period_snapshot = 'MONTHLY'",
            name="ck_payment_orders_billing_period_monthly",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PAID', 'EXPIRED', 'CANCELLED')",
            name="ck_payment_orders_status",
        ),
        CheckConstraint(
            "payment_code = upper(payment_code) AND payment_code ~ '^[A-Z0-9]+$'",
            name="ck_payment_orders_code_format",
        ),
        Index("ix_payment_orders_recruiter_status", "recruiter_id", "status"),
        Index("ix_payment_orders_status_expires", "status", "expires_at"),
        Index("ix_payment_orders_plan_id", "plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )
    plan_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_period_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_days_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    status: Mapped[PaymentOrderStatus] = mapped_column(
        String(16), nullable=False, default=PaymentOrderStatus.PENDING
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payment_transactions_amount_nonnegative"),
        CheckConstraint("provider = 'SEPAY'", name="ck_payment_transactions_provider"),
        CheckConstraint(
            "disposition IN ('APPLIED', 'UNMATCHED', 'AMOUNT_MISMATCH', "
            "'ORDER_EXPIRED', 'ORDER_CANCELLED', "
            "'OUTGOING_IGNORED', 'ACCOUNT_MISMATCH')",
            name="ck_payment_transactions_disposition",
        ),
        Index(
            "uq_payment_transactions_provider_transaction",
            "provider",
            "provider_transaction_id",
            unique=True,
        ),
        Index("ix_payment_transactions_order_id", "payment_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_orders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider: Mapped[PaymentProvider] = mapped_column(String(16), nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    disposition: Mapped[PaymentDisposition] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
