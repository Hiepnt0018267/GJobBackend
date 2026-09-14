from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.cv import (
    CVCertificateItem,
    CVEducationItem,
    CVExperienceItem,
    CVLanguageItem,
    CVPersonalInfo,
    CVProjectItem,
    CVSkillItem,
)


class StructuredCVExtractionResult(BaseModel):
    """Validated in-memory CV data aligned with the existing Builder contract."""

    model_config = ConfigDict(extra="forbid")

    personal_info: CVPersonalInfo = Field(default_factory=CVPersonalInfo)
    career_objective: str | None = Field(default=None, max_length=5000)
    educations: list[CVEducationItem] = Field(default_factory=list, max_length=100)
    experiences: list[CVExperienceItem] = Field(default_factory=list, max_length=100)
    skills: list[CVSkillItem] = Field(default_factory=list, max_length=100)
    projects: list[CVProjectItem] = Field(default_factory=list, max_length=100)
    certificates: list[CVCertificateItem] = Field(default_factory=list, max_length=100)
    languages: list[CVLanguageItem] = Field(default_factory=list, max_length=100)

    @field_validator("career_objective", mode="before")
    @classmethod
    def normalize_optional_objective(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value
