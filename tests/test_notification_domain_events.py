"""Task 16B transactional notification integration tests."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.admin_audit_log import AdminAuditLog
from app.models.application import JobApplication, JobApplicationStatus
from app.models.application_status_history import ApplicationStatusHistory
from app.models.cv import CV, CVSourceType
from app.models.job import Job, JobStatus, SalaryType
from app.models.notification import Notification, NotificationTargetType, NotificationType
from app.models.user import User, UserRole
from app.repositories.notification_repository import NotificationRepository
from app.schemas.application import JobApplicationCreate
from app.schemas.job import JobCreateRequest, JobUpdateRequest
from app.services.admin_job_service import AdminJobService
from app.services.application_service import ApplicationService
from app.services.candidate_application_service import CandidateApplicationService
from app.services.notification_event_service import (
    build_application_notification,
    build_job_notification,
)
from app.services.recruiter_application_service import RecruiterApplicationService
from app.services.recruiter_job_service import RecruiterJobService


EMAIL_PREFIX = "task16b_"
JOB_PREFIX = "__task16b__"


def _create_user(db, role: UserRole, label: str) -> User:
    user = User(
        email=f"{EMAIL_PREFIX}{label}_{uuid.uuid4().hex}@example.com",
        password_hash="not-used",
        full_name=f"Task 16B {label}",
        phone="0900000000" if role is UserRole.CANDIDATE else None,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def _create_job(
    db,
    recruiter_id: uuid.UUID | None,
    label: str,
    status: JobStatus = JobStatus.APPROVED,
) -> Job:
    job = Job(
        recruiter_id=recruiter_id,
        title=f"{JOB_PREFIX} {label}",
        description="Synthetic notification integration job",
        company_name="Task 16B Labs",
        status=status,
    )
    db.add(job)
    db.flush()
    return job


def _create_cv(db, candidate_id: uuid.UUID, label: str) -> CV:
    cv = CV(
        candidate_id=candidate_id,
        source_type=CVSourceType.UPLOADED,
        title=f"Task 16B {label}",
        storage_key=f"task16b/{uuid.uuid4()}.pdf",
        original_filename="synthetic.pdf",
        mime_type="application/pdf",
        file_size=128,
        uploaded_at=func.now(),
    )
    db.add(cv)
    db.flush()
    return cv


def _create_application(
    db,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    cv_id: uuid.UUID,
    status: JobApplicationStatus = JobApplicationStatus.SUBMITTED,
) -> JobApplication:
    application = JobApplication(
        candidate_id=candidate_id,
        job_id=job_id,
        cv_id=cv_id,
        status=status,
    )
    db.add(application)
    db.flush()
    db.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=None,
            to_status=status,
            changed_by_user_id=candidate_id,
        )
    )
    db.flush()
    return application


def _notification_rows(user_id: uuid.UUID | None = None) -> list[Notification]:
    db = SessionLocal()
    try:
        query = select(Notification).order_by(Notification.created_at, Notification.id)
        if user_id is not None:
            query = query.where(Notification.user_id == user_id)
        return list(db.scalars(query))
    finally:
        db.close()


def _notification_count() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(func.count(Notification.id))) or 0
    finally:
        db.close()


def _cleanup_task16b_records() -> None:
    db = SessionLocal()
    try:
        user_ids = list(
            db.scalars(select(User.id).where(User.email.like(f"{EMAIL_PREFIX}%")))
        )
        job_ids = list(
            db.scalars(select(Job.id).where(Job.title.like(f"{JOB_PREFIX}%")))
        )
        if user_ids:
            db.query(Notification).filter(Notification.user_id.in_(user_ids)).delete(
                synchronize_session=False
            )
        if job_ids:
            db.query(AdminAuditLog).filter(
                AdminAuditLog.entity_type == "JOB",
                AdminAuditLog.entity_id.in_(job_ids),
            ).delete(synchronize_session=False)
            db.query(JobApplication).filter(
                JobApplication.job_id.in_(job_ids)
            ).delete(synchronize_session=False)
        if user_ids:
            db.query(CV).filter(CV.candidate_id.in_(user_ids)).delete(
                synchronize_session=False
            )
        if job_ids:
            db.query(Job).filter(Job.id.in_(job_ids)).delete(
                synchronize_session=False
            )
        if user_ids:
            db.query(User).filter(User.id.in_(user_ids)).delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_task16b_records():
    _cleanup_task16b_records()
    yield
    _cleanup_task16b_records()


def _base_context() -> dict[str, uuid.UUID]:
    db = SessionLocal()
    try:
        candidate = _create_user(db, UserRole.CANDIDATE, "candidate")
        recruiter = _create_user(db, UserRole.RECRUITER, "recruiter")
        other_recruiter = _create_user(db, UserRole.RECRUITER, "other_recruiter")
        admin = _create_user(db, UserRole.ADMIN, "admin")
        cv = _create_cv(db, candidate.id, "CV")
        job = _create_job(db, recruiter.id, "Main")
        db.commit()
        return {
            "candidate": candidate.id,
            "recruiter": recruiter.id,
            "other_recruiter": other_recruiter.id,
            "admin": admin.id,
            "cv": cv.id,
            "job": job.id,
        }
    finally:
        db.close()


def _submit(context: dict[str, uuid.UUID], job_id: uuid.UUID | None = None):
    db = SessionLocal()
    try:
        candidate = db.get(User, context["candidate"])
        return ApplicationService(db).submit_application(
            candidate,
            job_id or context["job"],
            JobApplicationCreate(cv_id=context["cv"]),
        )
    finally:
        db.close()


def _transition(
    context: dict[str, uuid.UUID], application_id: uuid.UUID, action: str
):
    db = SessionLocal()
    try:
        recruiter = db.get(User, context["recruiter"])
        return RecruiterApplicationService(db).transition_application(
            recruiter, application_id, action
        )
    finally:
        db.close()


def test_exact_centralized_vietnamese_message_contract():
    job_title = "Kỹ sư Backend"
    def pair(copy):
        return copy.title, copy.message

    assert pair(
        build_application_notification(NotificationType.APPLICATION_SUBMITTED, job_title)
    ) == (
        "Bạn có ứng viên mới",
        "Có một ứng viên vừa nộp hồ sơ vào vị trí Kỹ sư Backend.",
    )
    expected_status_copy = {
        JobApplicationStatus.REVIEWING: (
            "Hồ sơ đang được xem xét",
            "Nhà tuyển dụng đang xem xét hồ sơ của bạn cho vị trí Kỹ sư Backend.",
        ),
        JobApplicationStatus.SHORTLISTED: (
            "Hồ sơ đã vào danh sách ưu tiên",
            "Hồ sơ của bạn đã được đưa vào danh sách ưu tiên cho vị trí Kỹ sư Backend.",
        ),
        JobApplicationStatus.REJECTED: (
            "Cập nhật hồ sơ ứng tuyển",
            "Hồ sơ của bạn chưa được chọn cho vị trí Kỹ sư Backend.",
        ),
        JobApplicationStatus.HIRED: (
            "Chúc mừng bạn",
            "Bạn đã được chọn cho vị trí Kỹ sư Backend.",
        ),
    }
    for application_status, expected in expected_status_copy.items():
        assert pair(
            build_application_notification(
                NotificationType.APPLICATION_STATUS_CHANGED,
                job_title,
                status=application_status,
            )
        ) == expected
    assert pair(
        build_application_notification(NotificationType.APPLICATION_WITHDRAWN, job_title)
    ) == (
        "Ứng viên đã rút hồ sơ",
        "Một ứng viên đã rút hồ sơ khỏi vị trí Kỹ sư Backend.",
    )
    assert pair(build_job_notification(NotificationType.JOB_APPROVED, job_title)) == (
        "Tin tuyển dụng đã được duyệt",
        "Tin tuyển dụng Kỹ sư Backend đã được phê duyệt.",
    )
    assert pair(build_job_notification(NotificationType.JOB_REJECTED, job_title)) == (
        "Tin tuyển dụng chưa được duyệt",
        "Tin tuyển dụng Kỹ sư Backend đã bị từ chối.",
    )
    sanitized = build_job_notification(
        NotificationType.JOB_APPROVED, "<strong>Kỹ sư</strong> Backend"
    )
    assert sanitized.message == "Tin tuyển dụng Kỹ sư Backend đã được phê duyệt."
    assert "<" not in sanitized.message


def test_frozen_application_event_matrix_recipients_targets_copy_and_idempotency():
    context = _base_context()
    primary = _submit(context)

    recruiter_rows = _notification_rows(context["recruiter"])
    assert len(recruiter_rows) == 1
    submitted = recruiter_rows[0]
    assert submitted.type == NotificationType.APPLICATION_SUBMITTED
    assert submitted.target_type == NotificationTargetType.APPLICATION
    assert submitted.target_id == primary.id
    assert submitted.read_at is None
    assert submitted.title == "Bạn có ứng viên mới"
    assert f"{JOB_PREFIX} Main" in submitted.message
    assert _notification_rows(context["candidate"]) == []
    assert _notification_rows(context["other_recruiter"]) == []
    assert _notification_rows(context["admin"]) == []

    expected_status_copy = {
        "review": (
            JobApplicationStatus.REVIEWING,
            "Hồ sơ đang được xem xét",
        ),
        "shortlist": (
            JobApplicationStatus.SHORTLISTED,
            "Hồ sơ đã vào danh sách ưu tiên",
        ),
        "hire": (JobApplicationStatus.HIRED, "Chúc mừng bạn"),
    }
    for action, (expected_status, expected_title) in expected_status_copy.items():
        result = _transition(context, primary.id, action)
        assert result.status is expected_status
        candidate_rows = _notification_rows(context["candidate"])
        assert candidate_rows[-1].type == NotificationType.APPLICATION_STATUS_CHANGED
        assert candidate_rows[-1].target_id == primary.id
        assert candidate_rows[-1].title == expected_title
        assert candidate_rows[-1].read_at is None
        if action == "review":
            count_before_repeat_review = _notification_count()
            with pytest.raises(HTTPException) as repeated_review:
                _transition(context, primary.id, "review")
            assert repeated_review.value.status_code == 409
            assert _notification_count() == count_before_repeat_review

    count_before_repeat = _notification_count()
    with pytest.raises(HTTPException) as repeated:
        _transition(context, primary.id, "hire")
    assert repeated.value.status_code == 409
    assert _notification_count() == count_before_repeat

    db = SessionLocal()
    try:
        reject_job = _create_job(db, context["recruiter"], "Reject")
        withdraw_job = _create_job(db, context["recruiter"], "Withdraw")
        db.commit()
        reject_job_id, withdraw_job_id = reject_job.id, withdraw_job.id
    finally:
        db.close()

    rejected_application = _submit(context, reject_job_id)
    rejected = _transition(context, rejected_application.id, "reject")
    assert rejected.status is JobApplicationStatus.REJECTED
    rejected_row = _notification_rows(context["candidate"])[-1]
    assert rejected_row.type == NotificationType.APPLICATION_STATUS_CHANGED
    assert rejected_row.title == "Cập nhật hồ sơ ứng tuyển"
    assert rejected_row.target_id == rejected_application.id

    withdrawn_application = _submit(context, withdraw_job_id)
    db = SessionLocal()
    try:
        candidate = db.get(User, context["candidate"])
        withdrawn = CandidateApplicationService(db).withdraw_application(
            candidate, withdrawn_application.id
        )
        assert withdrawn.status is JobApplicationStatus.WITHDRAWN
    finally:
        db.close()
    withdrawn_row = _notification_rows(context["recruiter"])[-1]
    assert withdrawn_row.type == NotificationType.APPLICATION_WITHDRAWN
    assert withdrawn_row.target_id == withdrawn_application.id
    assert withdrawn_row.title == "Ứng viên đã rút hồ sơ"
    count_before_repeat_withdraw = _notification_count()
    db = SessionLocal()
    try:
        candidate = db.get(User, context["candidate"])
        with pytest.raises(HTTPException) as repeated_withdraw:
            CandidateApplicationService(db).withdraw_application(
                candidate, withdrawn_application.id
            )
        assert repeated_withdraw.value.status_code == 409
    finally:
        db.close()
    assert _notification_count() == count_before_repeat_withdraw

    all_rows = [
        *_notification_rows(context["candidate"]),
        *_notification_rows(context["recruiter"]),
        *_notification_rows(context["other_recruiter"]),
        *_notification_rows(context["admin"]),
    ]
    forbidden_values = [
        f"{EMAIL_PREFIX}candidate",
        "0900000000",
        "synthetic.pdf",
        str(primary.id),
        str(context["candidate"]),
    ]
    rendered_content = " ".join(
        f"{row.title} {row.message}" for row in all_rows
    ).lower()
    assert all(value.lower() not in rendered_content for value in forbidden_values)


def test_invalid_application_transitions_and_duplicate_submit_create_no_notification():
    context = _base_context()
    application = _submit(context)
    initial_count = _notification_count()

    with pytest.raises(HTTPException) as invalid_transition:
        _transition(context, application.id, "shortlist")
    assert invalid_transition.value.status_code == 409
    assert _notification_count() == initial_count

    with pytest.raises(HTTPException) as duplicate_submit:
        _submit(context)
    assert duplicate_submit.value.status_code == 409
    assert _notification_count() == initial_count


def test_job_moderation_events_missing_owner_and_no_admin_pending_broadcast():
    context = _base_context()
    db = SessionLocal()
    try:
        approve_job = _create_job(
            db, context["recruiter"], "Approve", JobStatus.PENDING
        )
        reject_job = _create_job(
            db, context["recruiter"], "Reject moderation", JobStatus.PENDING
        )
        orphan_job = _create_job(db, None, "Orphan", JobStatus.PENDING)
        db.commit()
        approve_id, reject_id, orphan_id = (
            approve_job.id,
            reject_job.id,
            orphan_job.id,
        )
    finally:
        db.close()

    db = SessionLocal()
    try:
        admin = db.get(User, context["admin"])
        assert AdminJobService(db).approve_job(approve_id, admin).status is JobStatus.APPROVED
    finally:
        db.close()
    db = SessionLocal()
    try:
        admin = db.get(User, context["admin"])
        assert AdminJobService(db).reject_job(reject_id, admin).status is JobStatus.REJECTED
    finally:
        db.close()
    db = SessionLocal()
    try:
        admin = db.get(User, context["admin"])
        assert AdminJobService(db).approve_job(orphan_id, admin).status is JobStatus.APPROVED
    finally:
        db.close()

    recruiter_rows = _notification_rows(context["recruiter"])
    moderation_rows = [
        row
        for row in recruiter_rows
        if row.target_type == NotificationTargetType.JOB
    ]
    assert [(row.type, row.target_id) for row in moderation_rows] == [
        (NotificationType.JOB_APPROVED, approve_id),
        (NotificationType.JOB_REJECTED, reject_id),
    ]
    assert all(row.read_at is None for row in moderation_rows)
    assert _notification_rows(context["admin"]) == []
    assert not any(row.target_id == orphan_id for row in _notification_rows())

    for action, job_id in (("approve_job", approve_id), ("reject_job", reject_id)):
        before_repeat = _notification_count()
        db = SessionLocal()
        try:
            admin = db.get(User, context["admin"])
            with pytest.raises(HTTPException) as repeated:
                getattr(AdminJobService(db), action)(job_id, admin)
            assert repeated.value.status_code == 409
        finally:
            db.close()
        assert _notification_count() == before_repeat

    db = SessionLocal()
    try:
        recruiter = db.get(User, context["recruiter"])
        RecruiterJobService(db).create_job(
            recruiter,
            JobCreateRequest(
                title=f"{JOB_PREFIX} Pending no broadcast",
                description="No admin notification",
                company_name="Task 16B Labs",
                vacancies=1,
                salary_type=SalaryType.NEGOTIABLE,
                requirements="Synthetic requirements",
            ),
        )
        RecruiterJobService(db).update_job(
            recruiter,
            context["job"],
            JobUpdateRequest(description="Updated and returned to moderation"),
        )
    finally:
        db.close()
    assert _notification_rows(context["admin"]) == []


def _force_notification_failure(monkeypatch):
    def fail_create(*args, **kwargs):
        raise RuntimeError("synthetic notification insert failure")

    monkeypatch.setattr(NotificationRepository, "create", fail_create)


def test_submit_notification_failure_rolls_back_application_and_history(monkeypatch):
    context = _base_context()
    db = SessionLocal()
    try:
        history_count_before = db.scalar(
            select(func.count(ApplicationStatusHistory.id))
        )
        notification_count_before = db.scalar(select(func.count(Notification.id)))
    finally:
        db.close()
    _force_notification_failure(monkeypatch)

    with pytest.raises(RuntimeError, match="synthetic notification"):
        _submit(context)

    db = SessionLocal()
    try:
        assert db.scalar(
            select(func.count(JobApplication.id)).where(
                JobApplication.job_id == context["job"]
            )
        ) == 0
        assert db.scalar(select(func.count(ApplicationStatusHistory.id))) == history_count_before
        assert db.scalar(select(func.count(Notification.id))) == notification_count_before
    finally:
        db.close()


@pytest.mark.parametrize("operation", ["review", "withdraw"])
def test_application_mutation_notification_failure_rolls_back_status_and_history(
    monkeypatch, operation: str
):
    context = _base_context()
    db = SessionLocal()
    try:
        application = _create_application(
            db,
            context["candidate"],
            context["job"],
            context["cv"],
        )
        db.commit()
        application_id = application.id
    finally:
        db.close()
    notification_count_before = _notification_count()
    _force_notification_failure(monkeypatch)

    db = SessionLocal()
    try:
        actor_id = context["recruiter"] if operation == "review" else context["candidate"]
        actor = db.get(User, actor_id)
        with pytest.raises(RuntimeError, match="synthetic notification"):
            if operation == "review":
                RecruiterApplicationService(db).transition_application(
                    actor, application_id, "review"
                )
            else:
                CandidateApplicationService(db).withdraw_application(
                    actor, application_id
                )
    finally:
        db.close()

    db = SessionLocal()
    try:
        application = db.get(JobApplication, application_id)
        assert application.status is JobApplicationStatus.SUBMITTED
        histories = list(
            db.scalars(
                select(ApplicationStatusHistory).where(
                    ApplicationStatusHistory.application_id == application_id
                )
            )
        )
        assert len(histories) == 1
        assert histories[0].to_status is JobApplicationStatus.SUBMITTED
        assert db.scalar(select(func.count(Notification.id))) == notification_count_before
    finally:
        db.close()


@pytest.mark.parametrize(
    ("action", "expected_audit_action"),
    [("approve_job", "JOB_APPROVED"), ("reject_job", "JOB_REJECTED")],
)
def test_moderation_notification_failure_rolls_back_job_and_audit(
    monkeypatch, action: str, expected_audit_action: str
):
    context = _base_context()
    db = SessionLocal()
    try:
        job = _create_job(db, context["recruiter"], action, JobStatus.PENDING)
        db.commit()
        job_id = job.id
    finally:
        db.close()
    notification_count_before = _notification_count()
    _force_notification_failure(monkeypatch)

    db = SessionLocal()
    try:
        admin = db.get(User, context["admin"])
        with pytest.raises(RuntimeError, match="synthetic notification"):
            getattr(AdminJobService(db), action)(job_id, admin)
    finally:
        db.close()

    db = SessionLocal()
    try:
        assert db.get(Job, job_id).status is JobStatus.PENDING
        assert db.scalar(
            select(func.count(AdminAuditLog.id)).where(
                AdminAuditLog.entity_id == job_id,
                AdminAuditLog.action == expected_audit_action,
            )
        ) == 0
        assert db.scalar(select(func.count(Notification.id))) == notification_count_before
    finally:
        db.close()
