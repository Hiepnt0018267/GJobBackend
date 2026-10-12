import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NotificationType(StrEnum):
    SYSTEM = "SYSTEM"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    APPLICATION_STATUS_CHANGED = "APPLICATION_STATUS_CHANGED"
    APPLICATION_WITHDRAWN = "APPLICATION_WITHDRAWN"
    JOB_APPROVED = "JOB_APPROVED"
    JOB_REJECTED = "JOB_REJECTED"


class NotificationTargetType(StrEnum):
    APPLICATION = "APPLICATION"
    JOB = "JOB"
    CV = "CV"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(target_type IS NULL AND target_id IS NULL) OR "
            "(target_type IS NOT NULL AND target_id IS NOT NULL)",
            name="ck_notifications_target_pair",
        ),
        CheckConstraint(
            "char_length(btrim(title)) > 0",
            name="ck_notifications_title_not_blank",
        ),
        CheckConstraint(
            "char_length(btrim(message)) > 0",
            name="ck_notifications_message_not_blank",
        ),
        Index(
            "ix_notifications_user_created_id",
            "user_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_type: Mapped[NotificationTargetType | None] = mapped_column(
        String(32), nullable=True
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship()
