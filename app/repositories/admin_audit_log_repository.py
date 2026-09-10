import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.admin_audit_log import AdminAuditLog


class AdminAuditLogRepository:
    """Append-only admin audit persistence using the caller's transaction."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        *,
        admin_user_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        metadata: dict[str, Any] | None = None,
    ) -> AdminAuditLog:
        log = AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata or {},
        )
        self.db.add(log)
        return log
