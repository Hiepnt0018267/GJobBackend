"""create payment orders and provider transactions

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d2
Create Date: 2026-10-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4f6a8c0e1"
down_revision: Union[str, Sequence[str], None] = "a1c3e5f7b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recruiter_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("plan_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=0), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("billing_period_snapshot", sa.String(length=16), nullable=False),
        sa.Column("duration_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("payment_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_orders_amount_positive"),
        sa.CheckConstraint("currency = 'VND'", name="ck_payment_orders_currency_vnd"),
        sa.CheckConstraint("duration_days_snapshot > 0", name="ck_payment_orders_duration_positive"),
        sa.CheckConstraint(
            "billing_period_snapshot = 'MONTHLY'",
            name="ck_payment_orders_billing_period_monthly",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'EXPIRED', 'CANCELLED')",
            name="ck_payment_orders_status",
        ),
        sa.CheckConstraint(
            "payment_code = upper(payment_code) AND payment_code ~ '^[A-Z0-9]+$'",
            name="ck_payment_orders_code_format",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["subscription_plans.id"], name="fk_payment_orders_plan", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recruiter_id"], ["users.id"], name="fk_payment_orders_recruiter", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_orders_payment_code", "payment_orders", ["payment_code"], unique=True)
    op.create_index("ix_payment_orders_plan_id", "payment_orders", ["plan_id"])
    op.create_index("ix_payment_orders_recruiter_status", "payment_orders", ["recruiter_id", "status"])
    op.create_index("ix_payment_orders_status_expires", "payment_orders", ["status", "expires_at"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payment_order_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=0), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_code", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("destination_account", sa.String(length=128), nullable=True),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_payment_transactions_amount_nonnegative"),
        sa.CheckConstraint("provider = 'SEPAY'", name="ck_payment_transactions_provider"),
        sa.CheckConstraint(
            "disposition IN ('APPLIED', 'UNMATCHED', 'AMOUNT_MISMATCH', "
            "'ORDER_EXPIRED', 'ORDER_CANCELLED', "
            "'OUTGOING_IGNORED', 'ACCOUNT_MISMATCH')",
            name="ck_payment_transactions_disposition",
        ),
        sa.ForeignKeyConstraint(
            ["payment_order_id"],
            ["payment_orders.id"],
            name="fk_payment_transactions_order",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_transactions_order_id", "payment_transactions", ["payment_order_id"])
    op.create_index(
        "uq_payment_transactions_provider_transaction",
        "payment_transactions",
        ["provider", "provider_transaction_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_transactions_provider_transaction",
        table_name="payment_transactions",
    )
    op.drop_index("ix_payment_transactions_order_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index("ix_payment_orders_status_expires", table_name="payment_orders")
    op.drop_index("ix_payment_orders_recruiter_status", table_name="payment_orders")
    op.drop_index("ix_payment_orders_plan_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_payment_code", table_name="payment_orders")
    op.drop_table("payment_orders")
