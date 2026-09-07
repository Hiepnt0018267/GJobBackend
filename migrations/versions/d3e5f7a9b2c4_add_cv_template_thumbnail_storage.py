"""Add private managed thumbnail storage for CV templates.

Revision ID: d3e5f7a9b2c4
Revises: c9d2f4a7b6e1
"""

from alembic import op
import sqlalchemy as sa


revision = "d3e5f7a9b2c4"
down_revision = "c9d2f4a7b6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cv_templates", sa.Column("thumbnail_storage_key", sa.String(length=1024), nullable=True))
    op.create_unique_constraint("uq_cv_templates_thumbnail_storage_key", "cv_templates", ["thumbnail_storage_key"])


def downgrade() -> None:
    op.drop_constraint("uq_cv_templates_thumbnail_storage_key", "cv_templates", type_="unique")
    op.drop_column("cv_templates", "thumbnail_storage_key")
