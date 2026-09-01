import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CVTemplateLayoutKey(str, enum.Enum):
    MODERN = "MODERN"
    CLASSIC = "CLASSIC"
    MINIMAL = "MINIMAL"


class CVTemplate(Base):
    """Metadata for a frontend-supported CV renderer; never executable template code."""

    __tablename__ = "cv_templates"
    __table_args__ = (
        Index("ix_cv_templates_is_active", "is_active"),
        Index("ix_cv_templates_sort_order", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_key: Mapped[CVTemplateLayoutKey] = mapped_column(
        Enum(CVTemplateLayoutKey, name="cvtemplatelayoutkey"), nullable=False
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    cvs: Mapped[list["CV"]] = relationship(back_populates="template")

