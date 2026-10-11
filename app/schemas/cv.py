import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, get_args

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, PrivateAttr, ValidationInfo, field_validator, model_validator

from app.schemas.cv_template import CVTemplateSummary
from app.models.cv import CVSourceType
from app.models.cv_extraction import CVExtractionStatus
from app.schemas.partial_date import CVDate, definitely_reversed
from app.schemas.source_date_consistency import SourceDateConsistency, VerifiedSourceConflicts


class CVSkillLevel(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"


class CVLanguageProficiency(str, Enum):
    BASIC = "BASIC"
    CONVERSATIONAL = "CONVERSATIONAL"
    PROFESSIONAL = "PROFESSIONAL"
    FLUENT = "FLUENT"
    NATIVE = "NATIVE"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator('*', mode='before')
    @classmethod
    def normalize_absent_nullable(cls, value, info):
        if isinstance(value, str) and not value.strip() and type(None) in get_args(cls.model_fields[info.field_name].annotation):
            return None
        return value


def _trim_non_blank(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
    if value == "":
        raise ValueError("must not be blank")
    return value


def _trim_nullable_or_non_blank(cls, value, info):
    if isinstance(value, str) and not value.strip() and type(None) in get_args(cls.model_fields[info.field_name].annotation):
        return None
    return _trim_non_blank(value)


class CVPersonalInfo(_StrictModel):
    full_name: str | None = Field(
        default=None, max_length=255,
        description=("Only the candidate's explicitly stated personal name. "
                     "Never infer a name from job titles, headings, companies, skills, "
                     "professional summaries or anonymized placeholders. "
                     "Use null when no clear personal name is present."),
    )
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    avatar_url: HttpUrl | None = None
    date_of_birth: date | None = None
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None

    _trim_strings = field_validator("full_name", "phone", "address", mode="before")(_trim_nullable_or_non_blank)


class CVEducationItem(_StrictModel):
    school_name: str = Field(min_length=1, max_length=255)
    degree: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: CVDate | None = None
    end_date: CVDate | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=5000)

    _trim_strings = field_validator("school_name", "degree", "field_of_study", "description", mode="before")(_trim_nullable_or_non_blank)

    @model_validator(mode="after")
    def validate_dates(self):
        if definitely_reversed(self.start_date, self.end_date):
            raise ValueError("start_date must not be after end_date")
        return self


class CVExperienceItem(_StrictModel):
    company_name: str = Field(min_length=1, max_length=255)
    position: str = Field(min_length=1, max_length=255)
    start_date: CVDate | None = None
    end_date: CVDate | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=10000)
    date_consistency: SourceDateConsistency | None = Field(default=None,exclude_if=lambda value:value is None)
    _source_conflict_proof: object = PrivateAttr(default=None)

    _trim_strings = field_validator("company_name", "position", "description", mode="before")(_trim_nullable_or_non_blank)

    @model_validator(mode="after")
    def validate_dates(self,info:ValidationInfo):
        reversed_dates=definitely_reversed(self.start_date,self.end_date)
        if self.date_consistency is not None:
            proof=(info.context or {}).get('source_conflict_proof') or self._source_conflict_proof
            if not reversed_dates or not isinstance(proof,VerifiedSourceConflicts) or not proof.allows(self.model_dump(mode='json'),self.date_consistency):
                raise ValueError('SOURCE_DATA_CONFLICT requires verified source context')
            self._source_conflict_proof=proof
        elif reversed_dates:
            raise ValueError("start_date must not be after end_date")
        return self


class CVSkillItem(_StrictModel):
    name: str = Field(min_length=1, max_length=100)
    level: CVSkillLevel | None = None

    _trim_name = field_validator("name", mode="before")(_trim_non_blank)


class CVProjectItem(_StrictModel):
    name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    start_date: CVDate | None = None
    end_date: CVDate | None = None
    description: str | None = Field(default=None, max_length=10000)
    technologies: list[str] = Field(default_factory=list, max_length=100)
    project_url: HttpUrl | None = None

    _trim_strings = field_validator("name", "role", "description", mode="before")(_trim_nullable_or_non_blank)

    @field_validator("technologies", mode="before")
    @classmethod
    def validate_technologies(cls, value: Any):
        if not isinstance(value, list):
            raise ValueError("must be a list")
        return [_trim_non_blank(item) for item in value]

    @model_validator(mode="after")
    def validate_dates(self):
        if definitely_reversed(self.start_date, self.end_date):
            raise ValueError("start_date must not be after end_date")
        return self


class CVCertificateItem(_StrictModel):
    name: str = Field(min_length=1, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    issue_date: CVDate | None = None
    expiration_date: CVDate | None = None
    credential_url: HttpUrl | None = None

    _trim_strings = field_validator("name", "organization", mode="before")(_trim_nullable_or_non_blank)

    @model_validator(mode="after")
    def validate_dates(self):
        if definitely_reversed(self.issue_date, self.expiration_date):
            raise ValueError("issue_date must not be after expiration_date")
        return self


class CVLanguageItem(_StrictModel):
    name: str = Field(min_length=1, max_length=100)
    proficiency: CVLanguageProficiency | None = None

    _trim_name = field_validator("name", mode="before")(_trim_non_blank)


class CVCreateRequest(_StrictModel):
    title: str = Field(min_length=1, max_length=255)
    template_id: uuid.UUID
    personal_info: CVPersonalInfo = Field(default_factory=CVPersonalInfo)
    career_objective: str | None = Field(default=None, max_length=5000)
    educations: list[CVEducationItem] = Field(default_factory=list, max_length=100)
    experiences: list[CVExperienceItem] = Field(default_factory=list, max_length=100)
    skills: list[CVSkillItem] = Field(default_factory=list, max_length=100)
    projects: list[CVProjectItem] = Field(default_factory=list, max_length=100)
    certificates: list[CVCertificateItem] = Field(default_factory=list, max_length=100)
    languages: list[CVLanguageItem] = Field(default_factory=list, max_length=100)

    _trim_strings = field_validator("title", "career_objective", mode="before")(_trim_non_blank)


class CVUpdateRequest(_StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    template_id: uuid.UUID | None = None
    personal_info: CVPersonalInfo | None = None
    career_objective: str | None = Field(default=None, max_length=5000)
    educations: list[CVEducationItem] | None = Field(default=None, max_length=100)
    experiences: list[CVExperienceItem] | None = Field(default=None, max_length=100)
    skills: list[CVSkillItem] | None = Field(default=None, max_length=100)
    projects: list[CVProjectItem] | None = Field(default=None, max_length=100)
    certificates: list[CVCertificateItem] | None = Field(default=None, max_length=100)
    languages: list[CVLanguageItem] | None = Field(default=None, max_length=100)

    _trim_strings = field_validator("title", "career_objective", mode="before")(_trim_non_blank)


class CVUploadedFileMetadata(BaseModel):
    original_filename: str
    mime_type: str
    file_size: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CVListItem(BaseModel):
    id: uuid.UUID
    title: str
    is_default: bool
    source_type: CVSourceType
    template_id: uuid.UUID | None
    template: CVTemplateSummary | None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None = None
    has_managed_photo: bool = False
    created_at: datetime
    updated_at: datetime
    extraction_status: CVExtractionStatus | None = None
    extraction_error_code: str | None = None
    is_matchable: bool | None = None
    is_verified: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class CVListResponse(BaseModel):
    items: list[CVListItem]
    total: int


class CVResponse(CVListItem):
    personal_info: CVPersonalInfo
    career_objective: str | None
    educations: list[CVEducationItem]
    experiences: list[CVExperienceItem]
    skills: list[CVSkillItem]
    projects: list[CVProjectItem]
    certificates: list[CVCertificateItem]
    languages: list[CVLanguageItem]
