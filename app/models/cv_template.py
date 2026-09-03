import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CVTemplateLayoutKey(str, enum.Enum):
    MODERN = "MODERN"
    CLASSIC = "CLASSIC"
    MINIMAL = "MINIMAL"


class CVFontFamily(str, enum.Enum):
    INTER = "INTER"
    ARIAL = "ARIAL"
    TIMES_NEW_ROMAN = "TIMES_NEW_ROMAN"


class CVFontScale(str, enum.Enum):
    SMALL = "SMALL"
    NORMAL = "NORMAL"
    LARGE = "LARGE"


class CVSectionSpacing(str, enum.Enum):
    COMPACT = "COMPACT"
    NORMAL = "NORMAL"
    RELAXED = "RELAXED"


class CVHeadingStyle(str, enum.Enum):
    SOLID = "SOLID"
    UNDERLINE = "UNDERLINE"
    MINIMAL = "MINIMAL"


DEFAULT_CV_TEMPLATE_THEME_CONFIGS: dict[CVTemplateLayoutKey, dict[str, str]] = {
    CVTemplateLayoutKey.MODERN: {
        "primary_color": "#2563EB",
        "font_family": CVFontFamily.INTER.value,
        "font_scale": CVFontScale.NORMAL.value,
        "section_spacing": CVSectionSpacing.NORMAL.value,
        "heading_style": CVHeadingStyle.SOLID.value,
    },
    CVTemplateLayoutKey.CLASSIC: {
        "primary_color": "#0F172A",
        "font_family": CVFontFamily.INTER.value,
        "font_scale": CVFontScale.NORMAL.value,
        "section_spacing": CVSectionSpacing.NORMAL.value,
        "heading_style": CVHeadingStyle.UNDERLINE.value,
    },
    CVTemplateLayoutKey.MINIMAL: {
        "primary_color": "#334155",
        "font_family": CVFontFamily.INTER.value,
        "font_scale": CVFontScale.NORMAL.value,
        "section_spacing": CVSectionSpacing.COMPACT.value,
        "heading_style": CVHeadingStyle.MINIMAL.value,
    },
}


def default_cv_template_theme_config(layout_key: CVTemplateLayoutKey | str | None) -> dict[str, str]:
    try:
        normalized_layout = CVTemplateLayoutKey(layout_key or CVTemplateLayoutKey.MODERN)
    except ValueError:
        normalized_layout = CVTemplateLayoutKey.MODERN
    return dict(DEFAULT_CV_TEMPLATE_THEME_CONFIGS[normalized_layout])


def _theme_config_default(context) -> dict[str, str]:
    return default_cv_template_theme_config(context.get_current_parameters().get("layout_key"))


class CVTemplate(Base):
    """Metadata for a frontend-supported CV renderer; never executable template code."""

    __tablename__ = "cv_templates"
    __table_args__ = (
        Index("ix_cv_templates_is_active", "is_active"),
        Index("ix_cv_templates_is_deleted", "is_deleted"),
        Index("ix_cv_templates_sort_order", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_key: Mapped[CVTemplateLayoutKey] = mapped_column(
        Enum(CVTemplateLayoutKey, name="cvtemplatelayoutkey"), nullable=False
    )
    theme_config: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=_theme_config_default,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
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
