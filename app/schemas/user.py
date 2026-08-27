"""
User profile schemas (Task 03).
Separate from auth.py to keep Task 02 schemas untouched.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.user import UserRole


class UserProfile(BaseModel):
    """Full user profile response — never includes password_hash."""
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    phone: Optional[str]
    avatar_url: Optional[str]
    address: Optional[str]
    bio: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """
    PATCH /api/v1/users/me — only these fields can be updated.
    Role, is_active, email, password_hash are NOT accepted here.
    All fields are Optional so the client can send only what it wants to change.
    """
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("full_name must not be blank")
        return v.strip() if v else v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if v and not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
                raise ValueError("phone must contain digits, +, - or spaces only")
        return v or None
