"""create saved jobs

Revision ID: b9c3e7f1a5d2
Revises: a6b8d0e2f4c7
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c3e7f1a5d2"
down_revision: Union[str, Sequence[str], None] = "a6b8d0e2f4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["users.id"],
            name="fk_saved_jobs_candidate",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_saved_jobs_job",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_saved_jobs_candidate_job",
        ),
    )
    op.create_index(
        "ix_saved_jobs_candidate_created_at",
        "saved_jobs",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_saved_jobs_job_id",
        "saved_jobs",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_saved_jobs_job_id", table_name="saved_jobs")
    op.drop_index("ix_saved_jobs_candidate_created_at", table_name="saved_jobs")
    op.drop_table("saved_jobs")
