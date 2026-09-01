"""create CV template catalog

Revision ID: b7e13c4d9f02
Revises: 6f4d0c9a7b21
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7e13c4d9f02"
down_revision: Union[str, Sequence[str], None] = "6f4d0c9a7b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"
CLASSIC_TEMPLATE_ID = "10000000-0000-0000-0000-000000000002"
MINIMAL_TEMPLATE_ID = "10000000-0000-0000-0000-000000000003"


def upgrade() -> None:
    layout_key = postgresql.ENUM("MODERN", "CLASSIC", "MINIMAL", name="cvtemplatelayoutkey", create_type=False)
    layout_key.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "cv_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("layout_key", layout_key, nullable=False),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cv_templates_is_active", "cv_templates", ["is_active"], unique=False)
    op.create_index("ix_cv_templates_sort_order", "cv_templates", ["sort_order"], unique=False)
    op.bulk_insert(
        sa.table(
            "cv_templates",
            sa.column("id", sa.UUID()),
            sa.column("name", sa.String()),
            sa.column("description", sa.Text()),
            sa.column("layout_key", layout_key),
            sa.column("is_active", sa.Boolean()),
            sa.column("is_featured", sa.Boolean()),
            sa.column("sort_order", sa.Integer()),
        ),
        [
            {"id": MODERN_TEMPLATE_ID, "name": "Modern", "description": "Mẫu CV hiện đại, phù hợp công nghệ và startup.", "layout_key": "MODERN", "is_active": True, "is_featured": True, "sort_order": 1},
            {"id": CLASSIC_TEMPLATE_ID, "name": "Classic", "description": "Mẫu CV chuyên nghiệp, rõ ràng và truyền thống.", "layout_key": "CLASSIC", "is_active": True, "is_featured": False, "sort_order": 2},
            {"id": MINIMAL_TEMPLATE_ID, "name": "Minimal", "description": "Mẫu CV tối giản, tập trung vào nội dung.", "layout_key": "MINIMAL", "is_active": True, "is_featured": False, "sort_order": 3},
        ],
    )
    op.add_column("cvs", sa.Column("template_id", sa.UUID(), nullable=True))
    op.execute(sa.text(f"UPDATE cvs SET template_id = '{MODERN_TEMPLATE_ID}' WHERE template_id IS NULL"))
    op.alter_column("cvs", "template_id", nullable=False)
    op.create_foreign_key("fk_cvs_template_id_cv_templates", "cvs", "cv_templates", ["template_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_cvs_template_id", "cvs", ["template_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cvs_template_id", table_name="cvs")
    op.drop_constraint("fk_cvs_template_id_cv_templates", "cvs", type_="foreignkey")
    op.drop_column("cvs", "template_id")
    op.drop_index("ix_cv_templates_sort_order", table_name="cv_templates")
    op.drop_index("ix_cv_templates_is_active", table_name="cv_templates")
    op.drop_table("cv_templates")
    postgresql.ENUM(name="cvtemplatelayoutkey").drop(op.get_bind(), checkfirst=True)
