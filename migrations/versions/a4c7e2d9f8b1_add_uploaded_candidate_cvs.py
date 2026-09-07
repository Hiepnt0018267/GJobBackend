"""add uploaded candidate CV support

Revision ID: a4c7e2d9f8b1
Revises: f2b7c9d4e6a1
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a4c7e2d9f8b1"
down_revision: Union[str, Sequence[str], None] = "f2b7c9d4e6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


cv_source_type = postgresql.ENUM("BUILDER", "UPLOADED", name="cvsourcetype")


def upgrade() -> None:
    cv_source_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "cvs",
        sa.Column(
            "source_type",
            cv_source_type,
            nullable=False,
            server_default=sa.text("'BUILDER'"),
        ),
    )
    op.add_column("cvs", sa.Column("storage_key", sa.String(length=1024), nullable=True))
    op.add_column("cvs", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("cvs", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column("cvs", sa.Column("file_size", sa.BigInteger(), nullable=True))
    op.add_column("cvs", sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("cvs", "template_id", existing_type=sa.UUID(), nullable=True)
    op.create_unique_constraint("uq_cvs_storage_key", "cvs", ["storage_key"])
    op.create_check_constraint(
        "ck_cvs_source_metadata",
        "cvs",
        "(source_type = 'BUILDER' AND template_id IS NOT NULL AND storage_key IS NULL "
        "AND original_filename IS NULL AND mime_type IS NULL AND file_size IS NULL AND uploaded_at IS NULL) "
        "OR (source_type = 'UPLOADED' AND template_id IS NULL AND storage_key IS NOT NULL "
        "AND original_filename IS NOT NULL AND mime_type IS NOT NULL AND file_size IS NOT NULL AND uploaded_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM cvs WHERE source_type = 'UPLOADED') THEN
                RAISE EXCEPTION 'Cannot downgrade while uploaded CV records exist.';
            END IF;
        END $$;
        """
    )
    op.drop_constraint("ck_cvs_source_metadata", "cvs", type_="check")
    op.drop_constraint("uq_cvs_storage_key", "cvs", type_="unique")
    op.alter_column("cvs", "template_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("cvs", "uploaded_at")
    op.drop_column("cvs", "file_size")
    op.drop_column("cvs", "mime_type")
    op.drop_column("cvs", "original_filename")
    op.drop_column("cvs", "storage_key")
    op.drop_column("cvs", "source_type")
    cv_source_type.drop(op.get_bind(), checkfirst=True)
