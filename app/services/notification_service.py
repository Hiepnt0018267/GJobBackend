import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationTargetType, NotificationType
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.notification import (
    NotificationCreate,
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = NotificationRepository(db)
        self.user_repository = UserRepository(db)

    @staticmethod
    def _response(notification: Notification) -> NotificationResponse:
        return NotificationResponse(
            id=notification.id,
            type=notification.type,
            title=notification.title,
            message=notification.message,
            read_at=notification.read_at,
            is_read=notification.read_at is not None,
            target_type=notification.target_type,
            target_id=notification.target_id,
            created_at=notification.created_at,
        )

    def create_notification(
        self,
        recipient_user_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        target_type: NotificationTargetType | None = None,
        target_id: uuid.UUID | None = None,
    ) -> Notification:
        data = NotificationCreate(
            recipient_user_id=recipient_user_id,
            type=notification_type,
            title=title,
            message=message,
            target_type=target_type,
            target_id=target_id,
        )
        if self.user_repository.get_by_id(data.recipient_user_id) is None:
            raise ValueError("notification recipient does not exist")
        return self.repository.create(
            Notification(
                user_id=data.recipient_user_id,
                type=data.type,
                title=data.title,
                message=data.message,
                target_type=data.target_type,
                target_id=data.target_id,
            )
        )

    def list_notifications(
        self,
        current_user: User,
        *,
        page: int,
        page_size: int,
        unread_only: bool,
    ) -> NotificationListResponse:
        rows, total = self.repository.list_by_user(
            current_user.id,
            page=page,
            page_size=page_size,
            unread_only=unread_only,
        )
        return NotificationListResponse(
            items=[self._response(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def unread_count(self, current_user: User) -> NotificationUnreadCountResponse:
        return NotificationUnreadCountResponse(
            unread_count=self.repository.count_unread(current_user.id)
        )

    def mark_read(
        self, current_user: User, notification_id: uuid.UUID
    ) -> NotificationResponse:
        try:
            updated_id = self.repository.mark_read_atomic(
                current_user.id,
                notification_id,
                datetime.now(timezone.utc),
            )
            notification = self.repository.get_owned_by_id(
                current_user.id, updated_id or notification_id
            )
            if notification is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Notification not found.",
                )
            self.db.commit()
            self.db.refresh(notification)
            return self._response(notification)
        except HTTPException:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def mark_all_read(self, current_user: User) -> NotificationMarkAllReadResponse:
        try:
            updated_count = self.repository.mark_all_read(
                current_user.id, datetime.now(timezone.utc)
            )
            self.db.commit()
            return NotificationMarkAllReadResponse(updated_count=updated_count)
        except Exception:
            self.db.rollback()
            raise
