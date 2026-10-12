"""Task 16A shared multi-role notification foundation tests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.notification import Notification, NotificationTargetType, NotificationType
from app.models.user import User, UserRole
from app.schemas.notification import NotificationCreate
from app.services.notification_service import NotificationService


client = TestClient(app)
BASE = "/api/v1/notifications"
EMAIL_PREFIX = "task16a_"


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _create_user(role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"{EMAIL_PREFIX}{role.value.lower()}_{uuid.uuid4().hex}@example.com",
            password_hash="not-used",
            full_name=f"Task 16A {role.value.title()}",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _create_notification(
    user_id: uuid.UUID,
    *,
    title: str = "Task 16A notification",
    message: str = "Synthetic notification for foundation testing.",
    target_type: NotificationTargetType | None = None,
    target_id: uuid.UUID | None = None,
) -> Notification:
    db = SessionLocal()
    try:
        notification = NotificationService(db).create_notification(
            user_id,
            NotificationType.SYSTEM,
            title,
            message,
            target_type,
            target_id,
        )
        db.commit()
        db.refresh(notification)
        db.expunge(notification)
        return notification
    finally:
        db.close()


@pytest.fixture(autouse=True)
def cleanup_task16a_records():
    yield
    db = SessionLocal()
    try:
        user_ids = list(
            db.scalars(select(User.id).where(User.email.like(f"{EMAIL_PREFIX}%")))
        )
        if user_ids:
            db.query(Notification).filter(Notification.user_id.in_(user_ids)).delete(
                synchronize_session=False
            )
            db.query(User).filter(User.id.in_(user_ids)).delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()


def test_create_schema_enforces_text_enum_and_target_pair_contract():
    user_id = uuid.uuid4()
    target_id = uuid.uuid4()
    without_target = NotificationCreate(
        recipient_user_id=user_id,
        type=NotificationType.SYSTEM,
        title="  System notice  ",
        message="  Plain text body  ",
    )
    assert without_target.title == "System notice"
    assert without_target.message == "Plain text body"
    assert without_target.target_type is None
    assert without_target.target_id is None

    with_target = NotificationCreate(
        recipient_user_id=user_id,
        type="SYSTEM",
        title="System notice",
        message="Plain text body",
        target_type="JOB",
        target_id=target_id,
    )
    assert with_target.type is NotificationType.SYSTEM
    assert with_target.target_type is NotificationTargetType.JOB

    invalid_payloads = [
        {"title": "", "message": "message"},
        {"title": "   ", "message": "message"},
        {"title": "title", "message": ""},
        {"title": "title", "message": "   "},
        {"title": "<strong>title</strong>", "message": "message"},
        {"title": "title", "message": "<script>alert(1)</script>"},
        {"title": "title", "message": "message", "type": "UNKNOWN"},
        {
            "title": "title",
            "message": "message",
            "target_type": "CV",
        },
        {
            "title": "title",
            "message": "message",
            "target_id": target_id,
        },
    ]
    for extra in invalid_payloads:
        payload = {
            "recipient_user_id": user_id,
            "type": NotificationType.SYSTEM,
            **extra,
        }
        with pytest.raises(ValidationError):
            NotificationCreate(**payload)


def test_internal_creation_supports_all_roles_and_db_enforces_target_pair():
    users = [_create_user(role) for role in UserRole]
    db = SessionLocal()
    try:
        service = NotificationService(db)
        for user in users:
            notification = service.create_notification(
                user.id,
                NotificationType.SYSTEM,
                f"Notice for {user.role.value}",
                "Shared service, shared table.",
            )
            assert notification.user_id == user.id
        db.commit()
        assert db.scalar(select(Notification).where(Notification.user_id == users[0].id))

        db.add(
            Notification(
                user_id=users[0].id,
                type=NotificationType.SYSTEM,
                title="Invalid target",
                message="Target pair must remain consistent.",
                target_type=NotificationTargetType.JOB,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        with pytest.raises(ValueError, match="recipient"):
            service.create_notification(
                uuid.uuid4(),
                NotificationType.SYSTEM,
                "Missing recipient",
                "Must not create an orphan notification.",
            )
    finally:
        db.close()


def test_list_is_owned_for_candidate_recruiter_and_admin_with_no_admin_bypass():
    candidate = _create_user(UserRole.CANDIDATE)
    recruiter = _create_user(UserRole.RECRUITER)
    admin = _create_user(UserRole.ADMIN)
    for user in (candidate, recruiter, admin):
        _create_notification(user.id, title=f"Only {user.role.value}")

    for user in (candidate, recruiter, admin):
        response = client.get(BASE, headers=_headers(user.id))
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 1
        assert payload["page"] == 1
        assert payload["page_size"] == 20
        assert payload["total_pages"] == 1
        assert [item["title"] for item in payload["items"]] == [
            f"Only {user.role.value}"
        ]
        assert payload["items"][0]["is_read"] is False


def test_list_order_pagination_unread_filter_and_empty_contract():
    user = _create_user(UserRole.CANDIDATE)
    empty = client.get(BASE, headers=_headers(user.id)).json()
    assert empty == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }

    db = SessionLocal()
    try:
        same_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        low_id = uuid.UUID(int=1)
        high_id = uuid.UUID(int=2)
        older_id = uuid.UUID(int=3)
        db.add_all(
            [
                Notification(
                    id=low_id,
                    user_id=user.id,
                    type=NotificationType.SYSTEM,
                    title="same-low",
                    message="message",
                    created_at=same_time,
                ),
                Notification(
                    id=high_id,
                    user_id=user.id,
                    type=NotificationType.SYSTEM,
                    title="same-high",
                    message="message",
                    created_at=same_time,
                ),
                Notification(
                    id=older_id,
                    user_id=user.id,
                    type=NotificationType.SYSTEM,
                    title="older-read",
                    message="message",
                    created_at=same_time - timedelta(days=1),
                    read_at=same_time,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    page = client.get(
        BASE, params={"page": 1, "page_size": 2}, headers=_headers(user.id)
    )
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["total_pages"] == 2
    assert [item["title"] for item in page.json()["items"]] == [
        "same-high",
        "same-low",
    ]

    second = client.get(
        BASE, params={"page": 2, "page_size": 2}, headers=_headers(user.id)
    )
    assert [item["title"] for item in second.json()["items"]] == ["older-read"]

    unread = client.get(
        BASE, params={"unread_only": "true"}, headers=_headers(user.id)
    ).json()
    assert unread["total"] == 2
    assert all(item["is_read"] is False for item in unread["items"])

    assert client.get(
        BASE, params={"page_size": 100}, headers=_headers(user.id)
    ).status_code == 200
    assert client.get(
        BASE, params={"page_size": 101}, headers=_headers(user.id)
    ).status_code == 422
    assert client.get(
        BASE, params={"page": 0}, headers=_headers(user.id)
    ).status_code == 422


def test_unread_count_mark_one_is_atomic_idempotent_and_ownership_safe():
    owner = _create_user(UserRole.RECRUITER)
    foreign = _create_user(UserRole.ADMIN)
    notification = _create_notification(
        owner.id,
        target_type=NotificationTargetType.APPLICATION,
        target_id=uuid.uuid4(),
    )

    count = client.get(f"{BASE}/unread-count", headers=_headers(owner.id))
    assert count.status_code == 200
    assert count.json() == {"unread_count": 1}
    assert client.get(
        f"{BASE}/unread-count", headers=_headers(foreign.id)
    ).json() == {"unread_count": 0}

    first = client.patch(f"{BASE}/{notification.id}/read", headers=_headers(owner.id))
    assert first.status_code == 200, first.text
    first_read_at = first.json()["read_at"]
    assert first.json()["is_read"] is True
    assert first_read_at is not None

    second = client.patch(f"{BASE}/{notification.id}/read", headers=_headers(owner.id))
    assert second.status_code == 200
    assert second.json()["read_at"] == first_read_at
    assert client.get(
        f"{BASE}/unread-count", headers=_headers(owner.id)
    ).json() == {"unread_count": 0}

    foreign_result = client.patch(
        f"{BASE}/{notification.id}/read", headers=_headers(foreign.id)
    )
    missing_result = client.patch(
        f"{BASE}/{uuid.uuid4()}/read", headers=_headers(owner.id)
    )
    assert foreign_result.status_code == 404
    assert missing_result.status_code == 404
    assert foreign_result.json() == missing_result.json()


def test_mark_all_is_bulk_owned_preserves_read_rows_and_static_route_resolves():
    owner = _create_user(UserRole.CANDIDATE)
    other = _create_user(UserRole.RECRUITER)
    first = _create_notification(owner.id, title="first unread")
    second = _create_notification(owner.id, title="second unread")
    already_read = _create_notification(owner.id, title="already read")
    other_unread = _create_notification(other.id, title="other unread")

    original_read_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    db = SessionLocal()
    try:
        row = db.get(Notification, already_read.id)
        row.read_at = original_read_at
        db.commit()
    finally:
        db.close()

    response = client.patch(f"{BASE}/read-all", headers=_headers(owner.id))
    assert response.status_code == 200, response.text
    assert response.json() == {"updated_count": 2}

    db = SessionLocal()
    try:
        assert db.get(Notification, first.id).read_at is not None
        assert db.get(Notification, second.id).read_at is not None
        assert db.get(Notification, already_read.id).read_at == original_read_at
        assert db.get(Notification, other_unread.id).read_at is None
    finally:
        db.close()

    again = client.patch(f"{BASE}/read-all", headers=_headers(owner.id))
    assert again.status_code == 200
    assert again.json() == {"updated_count": 0}


def test_authentication_and_no_public_creation_endpoint():
    user = _create_user(UserRole.CANDIDATE)
    notification = _create_notification(user.id)
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/unread-count").status_code == 401
    assert client.patch(f"{BASE}/read-all").status_code == 401
    assert client.patch(f"{BASE}/{notification.id}/read").status_code == 401
    assert client.post(
        BASE,
        json={
            "user_id": str(user.id),
            "type": "SYSTEM",
            "title": "Forbidden",
            "message": "No public arbitrary creation.",
        },
        headers=_headers(user.id),
    ).status_code == 405

    openapi = client.get("/openapi.json").json()
    assert "post" not in openapi["paths"][BASE]
    list_parameters = {
        parameter["name"]
        for parameter in openapi["paths"][BASE]["get"]["parameters"]
    }
    assert "user_id" not in list_parameters
