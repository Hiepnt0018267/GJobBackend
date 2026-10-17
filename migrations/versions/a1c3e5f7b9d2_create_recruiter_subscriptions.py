"""create recruiter plan catalog and paid subscription history

Revision ID: a1c3e5f7b9d2
Revises: f8b2c4d6e1a3
Create Date: 2026-10-16
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c3e5f7b9d2"
down_revision: Union[str, Sequence[str], None] = "f8b2c4d6e1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(precision=18, scale=0), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("billing_period", sa.String(length=16), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("price >= 0", name="ck_subscription_plans_price_nonnegative"),
        sa.CheckConstraint(
            "duration_days IS NULL OR duration_days > 0",
            name="ck_subscription_plans_duration_positive",
        ),
        sa.CheckConstraint("currency = 'VND'", name="ck_subscription_plans_currency_vnd"),
        sa.CheckConstraint(
            "code = upper(code) AND code ~ '^[A-Z][A-Z0-9_]*$'",
            name="ck_subscription_plans_code_format",
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0",
            name="ck_subscription_plans_name_not_blank",
        ),
        sa.CheckConstraint(
            "billing_period IN ('NONE', 'MONTHLY')",
            name="ck_subscription_plans_billing_period",
        ),
        sa.CheckConstraint(
            "(code = 'FREE' AND price = 0 AND billing_period = 'NONE' AND duration_days IS NULL) "
            "OR (code <> 'FREE' AND price > 0 AND billing_period = 'MONTHLY' AND duration_days > 0)",
            name="ck_subscription_plans_semantics",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"], unique=True)

    op.create_table(
        "recruiter_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recruiter_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED', 'EXPIRED')",
            name="ck_recruiter_subscriptions_status",
        ),
        sa.CheckConstraint(
            "source IN ('ADMIN', 'PAYMENT')",
            name="ck_recruiter_subscriptions_source",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > starts_at",
            name="ck_recruiter_subscriptions_valid_interval",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["subscription_plans.id"],
            name="fk_recruiter_subscriptions_plan",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recruiter_id"],
            ["users.id"],
            name="fk_recruiter_subscriptions_recruiter",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recruiter_subscriptions_plan_id",
        "recruiter_subscriptions",
        ["plan_id"],
    )
    op.create_index(
        "ix_recruiter_subscriptions_recruiter_created",
        "recruiter_subscriptions",
        ["recruiter_id", "created_at"],
    )
    op.create_index(
        "uq_recruiter_subscriptions_one_active",
        "recruiter_subscriptions",
        ["recruiter_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    bind = op.get_bind()
    insert_default = sa.text(
        """
        INSERT INTO subscription_plans
            (id, code, name, description, price, currency, billing_period,
             duration_days, is_active, created_at, updated_at)
        VALUES
            (:id, :code, :name, NULL, :price, 'VND', :billing_period,
             :duration_days, true, now(), now())
        ON CONFLICT (code) DO NOTHING
        """
    )
    bind.execute(
        insert_default,
        {
            "id": uuid.UUID("10000000-0000-0000-0000-000000000101"),
            "code": "FREE",
            "name": "Miễn phí",
            "price": 0,
            "billing_period": "NONE",
            "duration_days": None,
        },
    )
    bind.execute(
        insert_default,
        {
            "id": uuid.UUID("10000000-0000-0000-0000-000000000102"),
            "code": "PRO_MONTHLY",
            "name": "PRO tháng",
            "price": 99000,
            "billing_period": "MONTHLY",
            "duration_days": 30,
        },
    )


def downgrade() -> None:
    op.drop_index("uq_recruiter_subscriptions_one_active", table_name="recruiter_subscriptions")
    op.drop_index("ix_recruiter_subscriptions_recruiter_created", table_name="recruiter_subscriptions")
    op.drop_index("ix_recruiter_subscriptions_plan_id", table_name="recruiter_subscriptions")
    op.drop_table("recruiter_subscriptions")
    op.drop_index("ix_subscription_plans_code", table_name="subscription_plans")
    op.drop_table("subscription_plans")
