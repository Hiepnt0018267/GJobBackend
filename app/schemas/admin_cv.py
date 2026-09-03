import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.cv_template import CVTemplateLayoutKey
from app.schemas.cv import (
    CVCertificateItem,
    CVEducationItem,
    CVExperienceItem,
    CVLanguageItem,
    CVPersonalInfo,
    CVProjectItem,
    CVSkillItem,
)
from app.schemas.cv_template import CVTemplateThemeConfig


class AdminCVCandidateSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class AdminCVTemplateSummary(BaseModel):
    id: uuid.UUID
    name: str
    layout_key: CVTemplateLayoutKey
    is_active: bool
    theme_config: CVTemplateThemeConfig

    model_config = ConfigDict(from_attributes=True)


class AdminCVListItem(BaseModel):
    id: uuid.UUID
    title: str
    is_default: bool
    candidate_id: uuid.UUID
    template_id: uuid.UUID
    candidate: AdminCVCandidateSummary
    template: AdminCVTemplateSummary
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminCVDetail(AdminCVListItem):
    personal_info: CVPersonalInfo
    career_objective: str | None
    educations: list[CVEducationItem]
    experiences: list[CVExperienceItem]
    skills: list[CVSkillItem]
    projects: list[CVProjectItem]
    certificates: list[CVCertificateItem]
    languages: list[CVLanguageItem]


class AdminCVListResponse(BaseModel):
    items: list[AdminCVListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
