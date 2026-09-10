"""add canonical skill taxonomy and job-skill projection

Revision ID: a6b8d0e2f4c7
Revises: f5a7c9d1e3b6
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6b8d0e2f4c7"
down_revision: Union[str, Sequence[str], None] = "f5a7c9d1e3b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_skills_normalized_name"),
    )
    op.create_table(
        "job_skills",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_job_skills_job", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name="fk_job_skills_skill", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_id", "skill_id"),
    )
    op.create_index(
        "ix_job_skills_skill_job",
        "job_skills",
        ["skill_id", "job_id"],
        unique=False,
    )

    # jobs.skills remains the stable API-facing source in this compatibility
    # phase. This projection trigger keeps normalized relational data complete
    # for every write path, including imports and maintenance scripts.
    op.execute(
        """
        CREATE FUNCTION sync_job_skills_from_array()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            raw_skill text;
            clean_name text;
            canonical_name text;
            canonical_skill_id uuid;
        BEGIN
            DELETE FROM job_skills WHERE job_id = NEW.id;

            IF NEW.skills IS NULL THEN
                RETURN NEW;
            END IF;

            FOREACH raw_skill IN ARRAY NEW.skills LOOP
                clean_name := btrim(regexp_replace(raw_skill, '[[:space:]]+', ' ', 'g'));
                canonical_name := lower(clean_name);

                IF canonical_name IS NULL OR canonical_name = '' THEN
                    CONTINUE;
                END IF;

                INSERT INTO skills (id, name, normalized_name, created_at, updated_at)
                VALUES (
                    (
                        substr(md5(canonical_name), 1, 8) || '-' ||
                        substr(md5(canonical_name), 9, 4) || '-' ||
                        substr(md5(canonical_name), 13, 4) || '-' ||
                        substr(md5(canonical_name), 17, 4) || '-' ||
                        substr(md5(canonical_name), 21, 12)
                    )::uuid,
                    clean_name,
                    canonical_name,
                    now(),
                    now()
                )
                ON CONFLICT (normalized_name)
                DO UPDATE SET name = skills.name
                RETURNING id INTO canonical_skill_id;

                INSERT INTO job_skills (job_id, skill_id, created_at)
                VALUES (NEW.id, canonical_skill_id, now())
                ON CONFLICT (job_id, skill_id) DO NOTHING;
            END LOOP;

            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_sync_job_skills_from_array
        AFTER INSERT OR UPDATE OF skills ON jobs
        FOR EACH ROW
        EXECUTE FUNCTION sync_job_skills_from_array()
        """
    )
    op.execute("UPDATE jobs SET skills = skills WHERE skills IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_job_skills_from_array ON jobs")
    op.execute("DROP FUNCTION IF EXISTS sync_job_skills_from_array()")
    op.drop_index("ix_job_skills_skill_job", table_name="job_skills")
    op.drop_table("job_skills")
    op.drop_table("skills")
