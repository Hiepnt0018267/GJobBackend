import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CVExtractionStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CVExtraction(Base):
    """One immutable-result extraction attempt for an uploaded candidate CV."""

    __tablename__ = "cv_extractions"
    __table_args__ = (
        CheckConstraint(
            "(status = 'PROCESSING' AND structured_result IS NULL "
            "AND error_code IS NULL AND failure_reason IS NULL AND completed_at IS NULL) "
            "OR (status = 'SUCCEEDED' AND structured_result IS NOT NULL "
            "AND error_code IS NULL AND failure_reason IS NULL AND completed_at IS NOT NULL) "
            "OR (status = 'FAILED' AND structured_result IS NULL "
            "AND error_code IS NOT NULL AND failure_reason IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_cv_extractions_status_payload",
        ),
        CheckConstraint(
            "confirmed_at IS NULL OR status = 'SUCCEEDED'",
            name="ck_cv_extractions_confirmation_status",
        ),
        Index("ix_cv_extractions_cv_created", "cv_id", "created_at"),
        Index(
            "uq_cv_extractions_active_cv",
            "cv_id",
            unique=True,
            postgresql_where=text("status = 'PROCESSING'"),
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
    status: Mapped[CVExtractionStatus] = mapped_column(
        Enum(CVExtractionStatus, name="cvextractionstatus"),
        nullable=False,
        default=CVExtractionStatus.PROCESSING,
        server_default=text("'PROCESSING'"),
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    structured_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    cv: Mapped["CV"] = relationship(back_populates="extractions")
