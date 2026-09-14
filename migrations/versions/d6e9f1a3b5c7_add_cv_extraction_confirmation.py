"""add CV extraction confirmation metadata

Revision ID: d6e9f1a3b5c7
Revises: c4d8e2f6a1b3
Create Date: 2026-09-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6e9f1a3b5c7"
down_revision: Union[str, Sequence[str], None] = "c4d8e2f6a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cv_extractions",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_cv_extractions_confirmation_status",
        "cv_extractions",
        "confirmed_at IS NULL OR status = 'SUCCEEDED'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cv_extractions_confirmation_status",
        "cv_extractions",
        type_="check",
    )
    op.drop_column("cv_extractions", "confirmed_at")
