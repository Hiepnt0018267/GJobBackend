import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.application import JobApplicationStatus


class ApplicationStatusHistory(Base):
    """Immutable audit timeline for a job application's status changes."""

    __tablename__ = "application_status_history"
    __table_args__ = (
        Index(
            "ix_application_status_history_application_created",
            "application_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[JobApplicationStatus | None] = mapped_column(
        Enum(JobApplicationStatus, name="jobapplicationstatus"), nullable=True
    )
    to_status: Mapped[JobApplicationStatus] = mapped_column(
        Enum(JobApplicationStatus, name="jobapplicationstatus"), nullable=False
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    application: Mapped["JobApplication"] = relationship(back_populates="status_history")
    changed_by_user: Mapped["User | None"] = relationship()
