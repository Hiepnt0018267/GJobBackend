import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.application import JobApplicationStatus
from app.models.notification import NotificationTargetType, NotificationType
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService


_HTML_TAG_PATTERN = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")


@dataclass(frozen=True)
class NotificationCopy:
    title: str
    message: str


_APPLICATION_STATUS_COPY: dict[JobApplicationStatus, tuple[str, str]] = {
    JobApplicationStatus.REVIEWING: (
        "Hồ sơ đang được xem xét",
        "Nhà tuyển dụng đang xem xét hồ sơ của bạn cho vị trí {job_title}.",
    ),
    JobApplicationStatus.SHORTLISTED: (
        "Hồ sơ đã vào danh sách ưu tiên",
        "Hồ sơ của bạn đã được đưa vào danh sách ưu tiên cho vị trí {job_title}.",
    ),
    JobApplicationStatus.REJECTED: (
        "Cập nhật hồ sơ ứng tuyển",
        "Hồ sơ của bạn chưa được chọn cho vị trí {job_title}.",
    ),
    JobApplicationStatus.HIRED: (
        "Chúc mừng bạn",
        "Bạn đã được chọn cho vị trí {job_title}.",
    ),
}


def _safe_job_title(job_title: str) -> str:
    plain_title = _HTML_TAG_PATTERN.sub("", job_title)
    plain_title = " ".join(plain_title.split())
    return plain_title or "tin tuyển dụng này"


def build_application_notification(
    notification_type: NotificationType,
    job_title: str,
    *,
    status: JobApplicationStatus | None = None,
) -> NotificationCopy:
    safe_title = _safe_job_title(job_title)
    if notification_type is NotificationType.APPLICATION_SUBMITTED:
        return NotificationCopy(
            title="Bạn có ứng viên mới",
            message=f"Có một ứng viên vừa nộp hồ sơ vào vị trí {safe_title}.",
        )
    if notification_type is NotificationType.APPLICATION_WITHDRAWN:
        return NotificationCopy(
            title="Ứng viên đã rút hồ sơ",
            message=f"Một ứng viên đã rút hồ sơ khỏi vị trí {safe_title}.",
        )
    if notification_type is NotificationType.APPLICATION_STATUS_CHANGED:
        if status not in _APPLICATION_STATUS_COPY:
            raise ValueError("unsupported application notification status")
        title, message_template = _APPLICATION_STATUS_COPY[status]
        return NotificationCopy(
            title=title,
            message=message_template.format(job_title=safe_title),
        )
    raise ValueError("unsupported application notification type")


def build_job_notification(
    notification_type: NotificationType, job_title: str
) -> NotificationCopy:
    safe_title = _safe_job_title(job_title)
    if notification_type is NotificationType.JOB_APPROVED:
        return NotificationCopy(
            title="Tin tuyển dụng đã được duyệt",
            message=f"Tin tuyển dụng {safe_title} đã được phê duyệt.",
        )
    if notification_type is NotificationType.JOB_REJECTED:
        return NotificationCopy(
            title="Tin tuyển dụng chưa được duyệt",
            message=f"Tin tuyển dụng {safe_title} đã bị từ chối.",
        )
    raise ValueError("unsupported job notification type")


class NotificationEventService:
    """Creates domain notifications in the caller-owned transaction."""

    def __init__(self, db: Session) -> None:
        self.user_repository = UserRepository(db)
        self.notification_service = NotificationService(db)

    def _create_if_recipient_exists(
        self,
        recipient_user_id: uuid.UUID | None,
        notification_type: NotificationType,
        copy: NotificationCopy,
        target_type: NotificationTargetType,
        target_id: uuid.UUID,
    ) -> bool:
        if recipient_user_id is None:
            return False
        if self.user_repository.get_by_id(recipient_user_id) is None:
            return False
        self.notification_service.create_notification(
            recipient_user_id,
            notification_type,
            copy.title,
            copy.message,
            target_type,
            target_id,
        )
        return True

    def create_application_notification(
        self,
        recipient_user_id: uuid.UUID | None,
        notification_type: NotificationType,
        application_id: uuid.UUID,
        job_title: str,
        *,
        status: JobApplicationStatus | None = None,
    ) -> bool:
        return self._create_if_recipient_exists(
            recipient_user_id,
            notification_type,
            build_application_notification(
                notification_type, job_title, status=status
            ),
            NotificationTargetType.APPLICATION,
            application_id,
        )

    def create_job_notification(
        self,
        recipient_user_id: uuid.UUID | None,
        notification_type: NotificationType,
        job_id: uuid.UUID,
        job_title: str,
    ) -> bool:
        return self._create_if_recipient_exists(
            recipient_user_id,
            notification_type,
            build_job_notification(notification_type, job_title),
            NotificationTargetType.JOB,
            job_id,
        )
