import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CVSourceType(str, enum.Enum):
    BUILDER = "BUILDER"
    UPLOADED = "UPLOADED"


class CV(Base):
    """A candidate-owned, structured CV document."""

    __tablename__ = "cvs"
    __table_args__ = (
        Index("ix_cvs_candidate_id_is_default", "candidate_id", "is_default"),
        Index(
            "uq_cvs_candidate_default",
            "candidate_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        CheckConstraint(
            "(source_type = 'BUILDER' AND template_id IS NOT NULL AND storage_key IS NULL "
            "AND original_filename IS NULL AND mime_type IS NULL AND file_size IS NULL AND uploaded_at IS NULL) "
            "OR (source_type = 'UPLOADED' AND template_id IS NULL AND storage_key IS NOT NULL "
            "AND original_filename IS NOT NULL AND mime_type IS NOT NULL AND file_size IS NOT NULL AND uploaded_at IS NOT NULL)",
            name="ck_cvs_source_metadata",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[CVSourceType] = mapped_column(
        Enum(CVSourceType, name="cvsourcetype"),
        nullable=False,
        default=CVSourceType.BUILDER,
        server_default=text("'BUILDER'"),
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cv_templates.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    # Uploaded CVs store only server-managed metadata. Never expose storage_key to clients.
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True, unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Builder CV photos are private managed assets. The key never leaves the API.
    photo_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True, unique=True)

    # Each JSONB column is validated by the API schemas before persistence.
    personal_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    career_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    educations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    experiences: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    projects: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    certificates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    languages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    candidate: Mapped["User"] = relationship(back_populates="cvs")
    template: Mapped["CVTemplate | None"] = relationship(back_populates="cvs")
    extractions: Mapped[list["CVExtraction"]] = relationship(
        back_populates="cv",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<CV id={self.id} candidate_id={self.candidate_id} title={self.title!r}>"

    @property
    def has_managed_photo(self) -> bool:
        return bool(self.photo_storage_key)
