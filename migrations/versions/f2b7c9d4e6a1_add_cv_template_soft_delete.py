"""add soft deletion for CV templates

Revision ID: f2b7c9d4e6a1
Revises: e4f6a8b2c1d3
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b7c9d4e6a1"
down_revision: Union[str, Sequence[str], None] = "e4f6a8b2c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cv_templates",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_cv_templates_is_deleted", "cv_templates", ["is_deleted"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cv_templates_is_deleted", table_name="cv_templates")
    op.drop_column("cv_templates", "is_deleted")
