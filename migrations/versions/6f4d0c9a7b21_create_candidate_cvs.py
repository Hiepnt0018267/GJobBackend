"""create candidate cvs

Revision ID: 6f4d0c9a7b21
Revises: 295df5fd2621
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "6f4d0c9a7b21"
down_revision: Union[str, Sequence[str], None] = "295df5fd2621"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cvs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("personal_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("career_objective", sa.Text(), nullable=True),
        sa.Column("educations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("experiences", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("projects", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("certificates", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cvs_id"), "cvs", ["id"], unique=False)
    op.create_index(op.f("ix_cvs_candidate_id"), "cvs", ["candidate_id"], unique=False)
    op.create_index("ix_cvs_candidate_id_is_default", "cvs", ["candidate_id", "is_default"], unique=False)
    op.create_index(
        "uq_cvs_candidate_default",
        "cvs",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_cvs_candidate_default", table_name="cvs")
    op.drop_index("ix_cvs_candidate_id_is_default", table_name="cvs")
    op.drop_index(op.f("ix_cvs_candidate_id"), table_name="cvs")
    op.drop_index(op.f("ix_cvs_id"), table_name="cvs")
    op.drop_table("cvs")
