"""create job applications

Revision ID: d8a4c1e5f903
Revises: b7e13c4d9f02
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d8a4c1e5f903"
down_revision: Union[str, Sequence[str], None] = "b7e13c4d9f02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    application_status = postgresql.ENUM(
        "SUBMITTED", "REVIEWING", "SHORTLISTED", "REJECTED", "HIRED", "WITHDRAWN",
        name="jobapplicationstatus", create_type=False,
    )
    application_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "job_applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("cv_id", sa.UUID(), nullable=False),
        sa.Column("status", application_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cv_id"], ["cvs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_job_applications_candidate_job"),
    )
    op.create_index("ix_job_applications_candidate_id", "job_applications", ["candidate_id"], unique=False)
    op.create_index("ix_job_applications_job_id", "job_applications", ["job_id"], unique=False)
    op.create_index("ix_job_applications_cv_id", "job_applications", ["cv_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_applications_cv_id", table_name="job_applications")
    op.drop_index("ix_job_applications_job_id", table_name="job_applications")
    op.drop_index("ix_job_applications_candidate_id", table_name="job_applications")
    op.drop_table("job_applications")
    postgresql.ENUM(name="jobapplicationstatus").drop(op.get_bind(), checkfirst=True)
