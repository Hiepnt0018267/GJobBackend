import uuid
from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.notification import NotificationTargetType, NotificationType


_HTML_TAG_PATTERN = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")


class NotificationCreate(BaseModel):
    recipient_user_id: uuid.UUID
    type: NotificationType
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    target_type: NotificationTargetType | None = None
    target_id: uuid.UUID | None = None

    @field_validator("title", "message")
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        if _HTML_TAG_PATTERN.search(value):
            raise ValueError("must be plain text")
        return value

    @model_validator(mode="after")
    def validate_target_pair(self) -> "NotificationCreate":
        if (self.target_type is None) != (self.target_id is None):
            raise ValueError("target_type and target_id must be provided together")
        return self


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    read_at: datetime | None
    is_read: bool
    target_type: NotificationTargetType | None
    target_id: uuid.UUID | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationMarkAllReadResponse(BaseModel):
    updated_count: int
