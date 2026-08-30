import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RecruiterProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str]
    company_name: Optional[str]
    company_website: Optional[str]
    company_description: Optional[str]
    company_address: Optional[str]
    company_logo_url: Optional[str]
    industry: Optional[str]
    company_size: Optional[int]
    created_at: datetime
    updated_at: datetime


class UpdateRecruiterProfileRequest(BaseModel):
    model_config = {"extra": "forbid"}

    full_name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    company_name: Optional[str] = Field(default=None, max_length=255)
    company_website: Optional[str] = Field(default=None, max_length=512)
    company_description: Optional[str] = None
    company_address: Optional[str] = Field(default=None, max_length=500)
    company_logo_url: Optional[str] = Field(default=None, max_length=512)
    industry: Optional[str] = Field(default=None, max_length=255)
    company_size: Optional[int] = Field(default=None, ge=1, le=10_000_000)

    @field_validator("company_name", "company_website", "company_description", "company_address", "company_logo_url", "industry", mode="before")
    @classmethod
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("full_name", mode="before")
    @classmethod
    def full_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("full_name must not be blank")
        return value.strip() if value else value

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if value and not value.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("phone must contain digits, +, - or spaces only")
        return value or None


class RecruiterDashboardSummary(BaseModel):
    total_jobs: int
    pending_jobs: int
    approved_jobs: int
    rejected_jobs: int
    closed_jobs: int
