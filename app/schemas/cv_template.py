import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.cv_template import (
    CVFontFamily,
    CVFontScale,
    CVHeadingStyle,
    CVSectionSpacing,
    CVTemplateLayoutKey,
)


class CVTemplateThemeConfig(BaseModel):
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: CVFontFamily
    font_scale: CVFontScale
    section_spacing: CVSectionSpacing
    heading_style: CVHeadingStyle

    model_config = ConfigDict(extra="forbid")


class CVTemplateSummary(BaseModel):
    id: uuid.UUID
    name: str
    layout_key: CVTemplateLayoutKey
    theme_config: CVTemplateThemeConfig
    is_featured: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class CVTemplatePublic(CVTemplateSummary):
    description: str | None
    thumbnail_url: HttpUrl | None


class CVTemplateCatalogResponse(BaseModel):
    items: list[CVTemplatePublic]
