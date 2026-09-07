"""add managed Builder CV photo storage reference

Revision ID: c9d2f4a7b6e1
Revises: a4c7e2d9f8b1
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d2f4a7b6e1"
down_revision: Union[str, Sequence[str], None] = "a4c7e2d9f8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cvs", sa.Column("photo_storage_key", sa.String(length=1024), nullable=True))
    op.create_unique_constraint("uq_cvs_photo_storage_key", "cvs", ["photo_storage_key"])


def downgrade() -> None:
    op.drop_constraint("uq_cvs_photo_storage_key", "cvs", type_="unique")
    op.drop_column("cvs", "photo_storage_key")
