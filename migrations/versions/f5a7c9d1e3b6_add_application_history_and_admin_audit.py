"""add application status history and admin audit logs

Revision ID: f5a7c9d1e3b6
Revises: e4f6a8b1c3d5
Create Date: 2026-09-08
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f5a7c9d1e3b6"
down_revision: Union[str, Sequence[str], None] = "e4f6a8b1c3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    application_status = postgresql.ENUM(
        "SUBMITTED",
        "REVIEWING",
        "SHORTLISTED",
        "REJECTED",
        "HIRED",
        "WITHDRAWN",
        name="jobapplicationstatus",
        create_type=False,
    )

    op.create_table(
        "application_status_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("from_status", application_status, nullable=True),
        sa.Column("to_status", application_status, nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["job_applications.id"],
            name="fk_application_status_history_application",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name="fk_application_status_history_changed_by_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_status_history_application_created",
        "application_status_history",
        ["application_id", "created_at"],
        unique=False,
    )

    history_table = sa.table(
        "application_status_history",
        sa.column("id", sa.UUID()),
        sa.column("application_id", sa.UUID()),
        sa.column("from_status", application_status),
        sa.column("to_status", application_status),
        sa.column("changed_by_user_id", sa.UUID()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    applications = list(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT id, candidate_id, status, created_at "
                "FROM job_applications ORDER BY created_at, id"
            )
        )
        .mappings()
    )
    if applications:
        op.bulk_insert(
            history_table,
            [
                {
                    "id": uuid.uuid4(),
                    "application_id": row["id"],
                    "from_status": None,
                    "to_status": row["status"],
                    "changed_by_user_id": row["candidate_id"],
                    "created_at": row["created_at"],
                }
                for row in applications
            ],
        )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("admin_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["users.id"],
            name="fk_admin_audit_logs_admin_user",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_logs_admin_created",
        "admin_audit_logs",
        ["admin_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_logs_entity",
        "admin_audit_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_logs_created_at",
        "admin_audit_logs",
        ["created_at"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_jobs_recruiter_id_users",
        "jobs",
        "users",
        ["recruiter_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_recruiter_id_users", "jobs", type_="foreignkey")
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_entity", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_admin_created", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_index(
        "ix_application_status_history_application_created",
        table_name="application_status_history",
    )
    op.drop_table("application_status_history")
