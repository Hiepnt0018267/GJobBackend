"""Task 16B.1 admin activity notification integration tests."""

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.job import Job, JobStatus, SalaryType
from app.models.notification import Notification, NotificationTargetType, NotificationType
from app.models.user import User, UserRole
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.job import JobCreateRequest, JobUpdateRequest
from app.services.admin_job_service import AdminJobService
from app.services.auth_service import AuthService
from app.services.notification_event_service import (
    build_job_notification,
    build_registration_notification,
)
from app.services.recruiter_job_service import RecruiterJobService


client = TestClient(app)
EMAIL_PREFIX = "task16b1_"
JOB_PREFIX = "__task16b1__"
NEW_TYPES = (
    NotificationType.CANDIDATE_REGISTERED,
    NotificationType.RECRUITER_REGISTERED,
    NotificationType.JOB_PENDING_REVIEW,
)


def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(Notification).filter(Notification.type.in_(NEW_TYPES)).delete(
            synchronize_session=False
        )
        job_ids = list(
            db.scalars(select(Job.id).where(Job.title.like(f"{JOB_PREFIX}%")))
        )
        if job_ids:
            db.query(AdminAuditLog).filter(
                AdminAuditLog.entity_type == "JOB",
                AdminAuditLog.entity_id.in_(job_ids),
            ).delete(synchronize_session=False)
            db.query(Notification).filter(
                Notification.target_type == NotificationTargetType.JOB,
                Notification.target_id.in_(job_ids),
            ).delete(synchronize_session=False)
            db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.email.like(f"{EMAIL_PREFIX}%")).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_task16b1_records():
    _cleanup()
    yield
    _cleanup()


def _create_user(
    role: UserRole,
    label: str,
    *,
    is_active: bool = True,
) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"{EMAIL_PREFIX}{label}_{uuid.uuid4().hex}@example.com",
            password_hash="not-used",
            full_name=f"Task 16B.1 {label}",
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _notifications(
    user_id: uuid.UUID,
    notification_type: NotificationType | None = None,
) -> list[Notification]:
    db = SessionLocal()
    try:
        query = select(Notification).where(Notification.user_id == user_id)
        if notification_type is not None:
            query = query.where(Notification.type == notification_type)
        return list(db.scalars(query.order_by(Notification.created_at, Notification.id)))
    finally:
        db.close()


def _job_payload(label: str) -> JobCreateRequest:
    return JobCreateRequest(
        title=f"{JOB_PREFIX} {label}",
        description="Synthetic admin notification job",
        company_name="Task 16B.1 Labs",
        vacancies=1,
        salary_type=SalaryType.NEGOTIABLE,
        requirements="Synthetic requirements",
    )


def test_new_types_and_centralized_copy_contract():
    assert NotificationType.CANDIDATE_REGISTERED.value == "CANDIDATE_REGISTERED"
    assert NotificationType.RECRUITER_REGISTERED.value == "RECRUITER_REGISTERED"
    assert NotificationType.JOB_PENDING_REVIEW.value == "JOB_PENDING_REVIEW"

    candidate = build_registration_notification(NotificationType.CANDIDATE_REGISTERED)
    recruiter = build_registration_notification(NotificationType.RECRUITER_REGISTERED)
    created = build_job_notification(
        NotificationType.JOB_PENDING_REVIEW,
        "Private title is deliberately unused",
        pending_source="create",
    )
    updated = build_job_notification(
        NotificationType.JOB_PENDING_REVIEW,
        "Private title is deliberately unused",
        pending_source="update",
    )
    assert (candidate.title, candidate.message) == (
        "Ứng viên mới đăng ký",
        "Có một tài khoản ứng viên mới vừa đăng ký.",
    )
    assert (recruiter.title, recruiter.message) == (
        "Nhà tuyển dụng mới đăng ký",
        "Có một tài khoản nhà tuyển dụng mới vừa đăng ký.",
    )
    assert created.title == "Có tin tuyển dụng mới chờ duyệt"
    assert updated.title == "Tin tuyển dụng đã được chỉnh sửa"
    assert created.message != updated.message


def test_active_admin_query_excludes_inactive_admins_and_non_admins():
    active_admin = _create_user(UserRole.ADMIN, "active_admin")
    inactive_admin = _create_user(
        UserRole.ADMIN, "inactive_admin", is_active=False
    )
    candidate = _create_user(UserRole.CANDIDATE, "candidate")
    db = SessionLocal()
    try:
        recipient_ids = set(UserRepository(db).list_active_admin_ids())
    finally:
        db.close()
    assert active_admin.id in recipient_ids
    assert inactive_admin.id not in recipient_ids
    assert candidate.id not in recipient_ids


def test_candidate_and_recruiter_registration_broadcast_only_to_active_admins():
    admin_a = _create_user(UserRole.ADMIN, "admin_a")
    admin_b = _create_user(UserRole.ADMIN, "admin_b")
    inactive_admin = _create_user(UserRole.ADMIN, "inactive", is_active=False)
    unrelated_recruiter = _create_user(UserRole.RECRUITER, "unrelated")

    candidate_email = f"{EMAIL_PREFIX}candidate_{uuid.uuid4().hex}@example.com"
    recruiter_email = f"{EMAIL_PREFIX}recruiter_{uuid.uuid4().hex}@example.com"
    candidate_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": candidate_email,
            "password": "password123",
            "full_name": "Private Candidate Name",
            "role": "CANDIDATE",
        },
    )
    recruiter_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": recruiter_email,
            "password": "password123",
            "full_name": "Private Recruiter Name",
            "role": "RECRUITER",
        },
    )
    assert candidate_response.status_code == 201, candidate_response.text
    assert recruiter_response.status_code == 201, recruiter_response.text

    candidate_id = uuid.UUID(candidate_response.json()["user"]["id"])
    recruiter_id = uuid.UUID(recruiter_response.json()["user"]["id"])
    for admin in (admin_a, admin_b):
        candidate_rows = _notifications(
            admin.id, NotificationType.CANDIDATE_REGISTERED
        )
        recruiter_rows = _notifications(
            admin.id, NotificationType.RECRUITER_REGISTERED
        )
        assert len(candidate_rows) == 1
        assert len(recruiter_rows) == 1
        assert candidate_rows[0].target_type is None
        assert candidate_rows[0].target_id is None
        assert recruiter_rows[0].target_type is None
        assert recruiter_rows[0].target_id is None
        rendered = " ".join(
            f"{row.title} {row.message}" for row in candidate_rows + recruiter_rows
        )
        assert candidate_email not in rendered
        assert recruiter_email not in rendered
        assert "Private Candidate Name" not in rendered
        assert "Private Recruiter Name" not in rendered

    assert _notifications(inactive_admin.id) == []
    assert _notifications(unrelated_recruiter.id) == []
    assert _notifications(candidate_id) == []
    assert _notifications(recruiter_id) == []


def test_job_create_and_new_review_cycle_broadcast_to_active_admins():
    admin_a = _create_user(UserRole.ADMIN, "admin_a")
    admin_b = _create_user(UserRole.ADMIN, "admin_b")
    inactive_admin = _create_user(UserRole.ADMIN, "inactive", is_active=False)
    recruiter = _create_user(UserRole.RECRUITER, "recruiter")

    db = SessionLocal()
    try:
        recruiter_row = db.get(User, recruiter.id)
        job = RecruiterJobService(db).create_job(
            recruiter_row, _job_payload("Review cycle")
        )
        job_id = job.id
    finally:
        db.close()

    for admin in (admin_a, admin_b):
        rows = _notifications(admin.id, NotificationType.JOB_PENDING_REVIEW)
        assert len(rows) == 1
        assert rows[0].target_type == NotificationTargetType.JOB.value
        assert rows[0].target_id == job_id
        assert rows[0].title == "Có tin tuyển dụng mới chờ duyệt"
    assert _notifications(inactive_admin.id) == []
    assert _notifications(recruiter.id, NotificationType.JOB_PENDING_REVIEW) == []

    db = SessionLocal()
    try:
        admin_row = db.get(User, admin_a.id)
        assert AdminJobService(db).approve_job(job_id, admin_row).status is JobStatus.APPROVED
    finally:
        db.close()
    db = SessionLocal()
    try:
        recruiter_row = db.get(User, recruiter.id)
        updated = RecruiterJobService(db).update_job(
            recruiter_row,
            job_id,
            JobUpdateRequest(description="A real second review cycle"),
        )
        assert updated.status is JobStatus.PENDING
    finally:
        db.close()

    for admin in (admin_a, admin_b):
        rows = _notifications(admin.id, NotificationType.JOB_PENDING_REVIEW)
        assert len(rows) == 2
        assert [row.title for row in rows] == [
            "Có tin tuyển dụng mới chờ duyệt",
            "Tin tuyển dụng đã được chỉnh sửa",
        ]
        assert all(row.target_id == job_id for row in rows)

    before_failed_update = {
        admin.id: len(_notifications(admin.id, NotificationType.JOB_PENDING_REVIEW))
        for admin in (admin_a, admin_b)
    }
    db = SessionLocal()
    try:
        recruiter_row = db.get(User, recruiter.id)
        with pytest.raises(HTTPException) as no_op:
            RecruiterJobService(db).update_job(
                recruiter_row, job_id, JobUpdateRequest()
            )
        assert no_op.value.status_code == 422
    finally:
        db.close()
    assert before_failed_update == {
        admin.id: len(_notifications(admin.id, NotificationType.JOB_PENDING_REVIEW))
        for admin in (admin_a, admin_b)
    }


def test_zero_active_admin_is_a_successful_empty_broadcast(monkeypatch):
    inactive_admin = _create_user(UserRole.ADMIN, "inactive", is_active=False)
    recruiter = _create_user(UserRole.RECRUITER, "recruiter")
    monkeypatch.setattr(UserRepository, "list_active_admin_ids", lambda self: [])

    email = f"{EMAIL_PREFIX}zero_admin_{uuid.uuid4().hex}@example.com"
    db = SessionLocal()
    try:
        candidate = AuthService(db).register(
            RegisterRequest(
                email=email,
                password="password123",
                full_name="Zero Admin Candidate",
                role=UserRole.CANDIDATE,
            )
        )
        candidate_id = candidate.id
    finally:
        db.close()
    db = SessionLocal()
    try:
        recruiter_row = db.get(User, recruiter.id)
        job = RecruiterJobService(db).create_job(
            recruiter_row, _job_payload("Zero admin")
        )
        job_id = job.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        assert db.get(User, candidate_id) is not None
        assert db.get(Job, job_id) is not None
    finally:
        db.close()
    assert _notifications(inactive_admin.id) == []


def _fail_second_notification(monkeypatch):
    original_create = NotificationRepository.create
    calls = 0

    def fail_second(self, notification):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic second admin notification failure")
        return original_create(self, notification)

    monkeypatch.setattr(NotificationRepository, "create", fail_second)


def test_registration_broadcast_failure_rolls_back_user_and_all_notifications(
    monkeypatch,
):
    admin_a = _create_user(UserRole.ADMIN, "admin_a")
    admin_b = _create_user(UserRole.ADMIN, "admin_b")
    email = f"{EMAIL_PREFIX}rollback_{uuid.uuid4().hex}@example.com"
    _fail_second_notification(monkeypatch)

    db = SessionLocal()
    try:
        with pytest.raises(RuntimeError, match="second admin"):
            AuthService(db).register(
                RegisterRequest(
                    email=email,
                    password="password123",
                    full_name="Rollback Candidate",
                    role=UserRole.CANDIDATE,
                )
            )
    finally:
        db.close()

    db = SessionLocal()
    try:
        assert db.scalar(select(User).where(User.email == email)) is None
    finally:
        db.close()
    assert _notifications(admin_a.id, NotificationType.CANDIDATE_REGISTERED) == []
    assert _notifications(admin_b.id, NotificationType.CANDIDATE_REGISTERED) == []


def test_job_broadcast_failure_rolls_back_job_and_all_notifications(monkeypatch):
    admin_a = _create_user(UserRole.ADMIN, "admin_a")
    admin_b = _create_user(UserRole.ADMIN, "admin_b")
    recruiter = _create_user(UserRole.RECRUITER, "recruiter")
    title = f"{JOB_PREFIX} rollback"
    _fail_second_notification(monkeypatch)

    db = SessionLocal()
    try:
        recruiter_row = db.get(User, recruiter.id)
        with pytest.raises(RuntimeError, match="second admin"):
            RecruiterJobService(db).create_job(
                recruiter_row,
                _job_payload("rollback"),
            )
    finally:
        db.close()

    db = SessionLocal()
    try:
        assert db.scalar(select(Job).where(Job.title == title)) is None
    finally:
        db.close()
    assert _notifications(admin_a.id, NotificationType.JOB_PENDING_REVIEW) == []
    assert _notifications(admin_b.id, NotificationType.JOB_PENDING_REVIEW) == []
