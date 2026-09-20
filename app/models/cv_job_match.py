"""Current derived matching result for one CV and one job."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CVJobMatch(Base):
    __tablename__ = "cv_job_matches"
    __table_args__ = (
        UniqueConstraint("cv_id", "job_id", name="uq_cv_job_matches_cv_job"),
        Index("ix_cv_job_matches_cv_id", "cv_id"),
        Index("ix_cv_job_matches_job_id", "job_id"),
        CheckConstraint(
            "baseline_status IN ('AVAILABLE', 'INSUFFICIENT_SIGNALS')",
            name="ck_cv_job_matches_baseline_status",
        ),
        CheckConstraint(
            "(baseline_status = 'AVAILABLE' AND baseline_result IS NOT NULL) OR "
            "(baseline_status = 'INSUFFICIENT_SIGNALS' AND baseline_result IS NULL)",
            name="ck_cv_job_matches_baseline_result_status",
        ),
        CheckConstraint(
            "semantic_similarity >= -1 AND semantic_similarity <= 1",
            name="ck_cv_job_matches_semantic_similarity",
        ),
        CheckConstraint(
            "embedding_dimensions > 0",
            name="ck_cv_job_matches_embedding_dimensions",
        ),
        CheckConstraint(
            "char_length(cv_fingerprint) = 64 AND char_length(job_fingerprint) = 64",
            name="ck_cv_job_matches_fingerprint_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cvs.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    baseline_status: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    semantic_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_model_config: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    cv_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    job_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
