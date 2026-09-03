import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.cv_template import CVTemplateLayoutKey
from app.schemas.cv_template import CVTemplateThemeConfig


class _CVTemplateMetadata(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    layout_key: CVTemplateLayoutKey
    thumbnail_url: HttpUrl | None = None
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AdminCVTemplateCreate(_CVTemplateMetadata):
    theme_config: CVTemplateThemeConfig | None = None
    is_active: bool = True
    is_featured: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_explicit_null_theme_config(self):
        if "theme_config" in self.model_fields_set and self.theme_config is None:
            raise ValueError("theme_config cannot be null")
        return self


class AdminCVTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    layout_key: CVTemplateLayoutKey | None = None
    thumbnail_url: HttpUrl | None = None
    sort_order: int | None = Field(default=None, ge=0)
    theme_config: CVTemplateThemeConfig | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def require_a_field(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one editable field.")
        if "theme_config" in self.model_fields_set and self.theme_config is None:
            raise ValueError("theme_config cannot be null")
        return self


class AdminCVTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    layout_key: CVTemplateLayoutKey
    theme_config: CVTemplateThemeConfig
    thumbnail_url: HttpUrl | None
    is_active: bool
    is_featured: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    usage_count: int


class AdminCVTemplateListResponse(BaseModel):
    items: list[AdminCVTemplateResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
