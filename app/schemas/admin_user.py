import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class AdminUserListItem(BaseModel):
    """Safe user fields used by the admin management list."""

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserDetailResponse(AdminUserListItem):
    """Safe profile fields available to an administrator for support purposes."""

    phone: str | None
    address: str | None
    bio: str | None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
