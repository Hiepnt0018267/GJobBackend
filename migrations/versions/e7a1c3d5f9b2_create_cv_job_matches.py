"""create current derived CV/job matches

Revision ID: e7a1c3d5f9b2
Revises: d6e9f1a3b5c7
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e7a1c3d5f9b2"
down_revision: Union[str, Sequence[str], None] = "d6e9f1a3b5c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cv_job_matches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cv_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("baseline_status", sa.String(length=32), nullable=False),
        sa.Column(
            "baseline_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("semantic_similarity", sa.Float(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_model_config", sa.String(length=255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("baseline_engine_version", sa.String(length=64), nullable=False),
        sa.Column("semantic_engine_version", sa.String(length=64), nullable=False),
        sa.Column("cv_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("job_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
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
            "baseline_status IN ('AVAILABLE', 'INSUFFICIENT_SIGNALS')",
            name="ck_cv_job_matches_baseline_status",
        ),
        sa.CheckConstraint(
            "(baseline_status = 'AVAILABLE' AND baseline_result IS NOT NULL) OR "
            "(baseline_status = 'INSUFFICIENT_SIGNALS' AND baseline_result IS NULL)",
            name="ck_cv_job_matches_baseline_result_status",
        ),
        sa.CheckConstraint(
            "semantic_similarity >= -1 AND semantic_similarity <= 1",
            name="ck_cv_job_matches_semantic_similarity",
        ),
        sa.CheckConstraint(
            "embedding_dimensions > 0",
            name="ck_cv_job_matches_embedding_dimensions",
        ),
        sa.CheckConstraint(
            "char_length(cv_fingerprint) = 64 AND char_length(job_fingerprint) = 64",
            name="ck_cv_job_matches_fingerprint_length",
        ),
        sa.ForeignKeyConstraint(
            ["cv_id"],
            ["cvs.id"],
            name="fk_cv_job_matches_cv",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="fk_cv_job_matches_job",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cv_id", "job_id", name="uq_cv_job_matches_cv_job"),
    )
    op.create_index("ix_cv_job_matches_cv_id", "cv_job_matches", ["cv_id"])
    op.create_index("ix_cv_job_matches_job_id", "cv_job_matches", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_job_matches_job_id", table_name="cv_job_matches")
    op.drop_index("ix_cv_job_matches_cv_id", table_name="cv_job_matches")
    op.drop_table("cv_job_matches")
