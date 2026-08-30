"""add recruiter profiles

Revision ID: c7e9d4a31f2b
Revises: 8ba721abef74
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e9d4a31f2b"
down_revision: Union[str, Sequence[str], None] = "8ba721abef74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recruiter_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("company_website", sa.String(length=512), nullable=True),
        sa.Column("company_description", sa.Text(), nullable=True),
        sa.Column("company_address", sa.String(length=500), nullable=True),
        sa.Column("company_logo_url", sa.String(length=512), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("company_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_recruiter_profiles_id"), "recruiter_profiles", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recruiter_profiles_id"), table_name="recruiter_profiles")
    op.drop_table("recruiter_profiles")
