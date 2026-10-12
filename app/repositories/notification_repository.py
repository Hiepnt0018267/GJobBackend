import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.flush()
        return notification

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        unread_only: bool,
    ) -> tuple[list[Notification], int]:
        filters = [Notification.user_id == user_id]
        if unread_only:
            filters.append(Notification.read_at.is_(None))

        total = self.db.scalar(
            select(func.count(Notification.id)).where(*filters)
        ) or 0
        items = list(
            self.db.scalars(
                select(Notification)
                .where(*filters)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def get_owned_by_id(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification | None:
        return self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )

    def count_unread(self, user_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        ) or 0

    def mark_read_atomic(
        self,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
        read_at: datetime,
    ) -> uuid.UUID | None:
        return self.db.scalar(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=read_at)
            .returning(Notification.id)
        )

    def mark_all_read(self, user_id: uuid.UUID, read_at: datetime) -> int:
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=read_at)
        )
        return result.rowcount or 0
