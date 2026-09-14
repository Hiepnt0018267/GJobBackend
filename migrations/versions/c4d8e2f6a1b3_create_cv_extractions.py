"""create CV extraction attempts

Revision ID: c4d8e2f6a1b3
Revises: b9c3e7f1a5d2
Create Date: 2026-09-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4d8e2f6a1b3"
down_revision: Union[str, Sequence[str], None] = "b9c3e7f1a5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = postgresql.ENUM(
        "PROCESSING",
        "SUCCEEDED",
        "FAILED",
        name="cvextractionstatus",
        create_type=False,
    )
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "cv_extractions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cv_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            status_enum,
            server_default=sa.text("'PROCESSING'"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("structured_result", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'PROCESSING' AND structured_result IS NULL "
            "AND error_code IS NULL AND failure_reason IS NULL AND completed_at IS NULL) "
            "OR (status = 'SUCCEEDED' AND structured_result IS NOT NULL "
            "AND error_code IS NULL AND failure_reason IS NULL AND completed_at IS NOT NULL) "
            "OR (status = 'FAILED' AND structured_result IS NULL "
            "AND error_code IS NOT NULL AND failure_reason IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_cv_extractions_status_payload",
        ),
        sa.ForeignKeyConstraint(
            ["cv_id"],
            ["cvs.id"],
            name="fk_cv_extractions_cv",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cv_extractions_cv_created",
        "cv_extractions",
        ["cv_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_cv_extractions_active_cv",
        "cv_extractions",
        ["cv_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PROCESSING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_cv_extractions_active_cv", table_name="cv_extractions")
    op.drop_index("ix_cv_extractions_cv_created", table_name="cv_extractions")
    op.drop_table("cv_extractions")
    postgresql.ENUM(name="cvextractionstatus").drop(op.get_bind(), checkfirst=True)
