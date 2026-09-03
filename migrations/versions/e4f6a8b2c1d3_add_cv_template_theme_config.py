"""add typed theme configuration to CV templates

Revision ID: e4f6a8b2c1d3
Revises: d8a4c1e5f903
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4f6a8b2c1d3"
down_revision: Union[str, Sequence[str], None] = "d8a4c1e5f903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cv_templates", sa.Column("theme_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE cv_templates
            SET theme_config = CASE layout_key::text
                WHEN 'CLASSIC' THEN '{"primary_color":"#0F172A","font_family":"INTER","font_scale":"NORMAL","section_spacing":"NORMAL","heading_style":"UNDERLINE"}'::jsonb
                WHEN 'MINIMAL' THEN '{"primary_color":"#334155","font_family":"INTER","font_scale":"NORMAL","section_spacing":"COMPACT","heading_style":"MINIMAL"}'::jsonb
                ELSE '{"primary_color":"#2563EB","font_family":"INTER","font_scale":"NORMAL","section_spacing":"NORMAL","heading_style":"SOLID"}'::jsonb
            END
            WHERE theme_config IS NULL
            """
        )
    )
    op.alter_column("cv_templates", "theme_config", nullable=False)


def downgrade() -> None:
    op.drop_column("cv_templates", "theme_config")
