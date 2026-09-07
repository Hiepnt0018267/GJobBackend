"""Store the original filename of managed CV-template thumbnails."""

from alembic import op
import sqlalchemy as sa

revision = "e4f6a8b1c3d5"
down_revision = "d3e5f7a9b2c4"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("cv_templates", sa.Column("thumbnail_original_filename", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("cv_templates", "thumbnail_original_filename")
