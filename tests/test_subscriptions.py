import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.main import app
from app.models.subscription import (
    BillingPeriod,
    RecruiterSubscription,
    SubscriptionPlan,
    SubscriptionSource,
    SubscriptionStatus,
)
from app.models.user import User, UserRole
from app.schemas.subscription import SubscriptionGrantRequest
from app.services.subscription_service import SubscriptionService


client = TestClient(app)
ADMIN_PLANS = "/api/v1/admin/subscription-plans"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"mon01a_{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name=f"Monetization {role.value}",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _token(role: UserRole) -> tuple[User, str]:
    user = _create_user(role)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return user, response.json()["access_token"]


def _plan(code: str = "PRO_MONTHLY") -> SubscriptionPlan:
    db = SessionLocal()
    try:
        plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == code))
        assert plan is not None
        db.expunge(plan)
        return plan
    finally:
        db.close()


def _cleanup() -> None:
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like("mon01a_%@example.com"))))
        if user_ids:
            db.query(RecruiterSubscription).filter(
                RecruiterSubscription.recruiter_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        custom_plan_ids = list(
            db.scalars(select(SubscriptionPlan.id).where(SubscriptionPlan.code.like("TEST_%")))
        )
        if custom_plan_ids:
            db.query(RecruiterSubscription).filter(
                RecruiterSubscription.plan_id.in_(custom_plan_ids)
            ).delete(synchronize_session=False)
            db.query(SubscriptionPlan).filter(SubscriptionPlan.id.in_(custom_plan_ids)).delete(
                synchronize_session=False
            )
        db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "FREE").update(
            {
                SubscriptionPlan.name: "Miễn phí",
                SubscriptionPlan.description: None,
                SubscriptionPlan.price: Decimal("0"),
                SubscriptionPlan.currency: "VND",
                SubscriptionPlan.billing_period: BillingPeriod.NONE,
                SubscriptionPlan.duration_days: None,
                SubscriptionPlan.is_active: True,
            },
            synchronize_session=False,
        )
        db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "PRO_MONTHLY").update(
            {
                SubscriptionPlan.name: "PRO tháng",
                SubscriptionPlan.description: None,
                SubscriptionPlan.price: Decimal("99000"),
                SubscriptionPlan.currency: "VND",
                SubscriptionPlan.billing_period: BillingPeriod.MONTHLY,
                SubscriptionPlan.duration_days: 30,
                SubscriptionPlan.is_active: True,
            },
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_monetization_data():
    _cleanup()
    yield
    _cleanup()


def test_seeded_catalog_and_plan_api_authorization() -> None:
    free = _plan("FREE")
    pro = _plan("PRO_MONTHLY")
    assert free.price == Decimal("0")
    assert free.billing_period == BillingPeriod.NONE
    assert free.duration_days is None
    assert pro.price == Decimal("99000")
    assert pro.billing_period == BillingPeriod.MONTHLY
    assert pro.duration_days == 30

    _, candidate_token = _token(UserRole.CANDIDATE)
    _, recruiter_token = _token(UserRole.RECRUITER)
    _, admin_token = _token(UserRole.ADMIN)
    assert client.get(ADMIN_PLANS).status_code == 401
    assert client.get(ADMIN_PLANS, headers=_headers(candidate_token)).status_code == 403
    assert client.get(ADMIN_PLANS, headers=_headers(recruiter_token)).status_code == 403
    response = client.get(ADMIN_PLANS, headers=_headers(admin_token))
    assert response.status_code == 200
    assert {item["code"] for item in response.json()["items"]} >= {"FREE", "PRO_MONTHLY"}


def test_plan_create_validation_duplicate_and_pagination() -> None:
    _, admin_token = _token(UserRole.ADMIN)
    payload = {
        "code": " test_pro_30 ",
        "name": "Test Pro 30",
        "price": "150000",
        "currency": "vnd",
        "billing_period": "MONTHLY",
        "duration_days": 30,
        "is_active": True,
    }
    created = client.post(ADMIN_PLANS, headers=_headers(admin_token), json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["code"] == "TEST_PRO_30"
    assert created.json()["price"] == "150000"
    assert client.post(ADMIN_PLANS, headers=_headers(admin_token), json=payload).status_code == 409

    for invalid in (
        {**payload, "code": "TEST_NEGATIVE", "price": "-1"},
        {**payload, "code": "TEST_ZERO", "price": "0"},
        {**payload, "code": "TEST_DURATION", "duration_days": 0},
        {**payload, "code": "TEST_NONE", "billing_period": "NONE"},
        {**payload, "code": "TEST_CURRENCY", "currency": "USD"},
    ):
        assert client.post(ADMIN_PLANS, headers=_headers(admin_token), json=invalid).status_code == 422

    listed = client.get(
        ADMIN_PLANS,
        params={"is_active": True, "page": 1, "page_size": 2},
        headers=_headers(admin_token),
    )
    assert listed.status_code == 200
    assert listed.json()["page_size"] == 2
    assert len(listed.json()["items"]) == 2
    plan_id = created.json()["id"]
    assert client.get(f"{ADMIN_PLANS}/{plan_id}", headers=_headers(admin_token)).status_code == 200
    assert client.delete(f"{ADMIN_PLANS}/{plan_id}", headers=_headers(admin_token)).status_code == 405


def test_free_fallback_for_recruiter_only_and_never_creates_free_history() -> None:
    recruiter, recruiter_token = _token(UserRole.RECRUITER)
    _, candidate_token = _token(UserRole.CANDIDATE)
    _, admin_token = _token(UserRole.ADMIN)

    response = client.get("/api/v1/recruiter/subscription", headers=_headers(recruiter_token))
    assert response.status_code == 200
    assert response.json()["effective_plan"]["code"] == "FREE"
    assert response.json()["subscription"] is None
    assert client.get("/api/v1/recruiter/subscription", headers=_headers(candidate_token)).status_code == 403
    assert client.get("/api/v1/recruiter/subscription", headers=_headers(admin_token)).status_code == 403

    db = SessionLocal()
    try:
        assert db.scalar(
            select(func.count(RecruiterSubscription.id)).where(
                RecruiterSubscription.recruiter_id == recruiter.id
            )
        ) == 0
    finally:
        db.close()


def test_grant_default_dates_explicit_precedence_and_invalid_interval() -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    _, admin_token = _token(UserRole.ADMIN)
    plan = _plan()
    before = datetime.now(timezone.utc)
    granted = client.post(
        f"/api/v1/admin/recruiters/{recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={"plan_id": str(plan.id)},
    )
    after = datetime.now(timezone.utc)
    assert granted.status_code == 200, granted.text
    body = granted.json()
    starts_at = datetime.fromisoformat(body["subscription"]["starts_at"])
    expires_at = datetime.fromisoformat(body["subscription"]["expires_at"])
    assert before <= starts_at <= after
    assert expires_at == starts_at + timedelta(days=30)
    assert body["subscription"]["source"] == "ADMIN"
    assert body["effective_plan"]["code"] == "PRO_MONTHLY"

    explicit_start = datetime.now(timezone.utc) - timedelta(days=2)
    explicit_expiry = explicit_start + timedelta(days=5)
    changed = client.post(
        f"/api/v1/admin/recruiters/{recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={
            "plan_id": str(plan.id),
            "starts_at": explicit_start.isoformat(),
            "expires_at": explicit_expiry.isoformat(),
        },
    )
    assert changed.status_code == 200
    assert datetime.fromisoformat(changed.json()["subscription"]["expires_at"]) == explicit_expiry

    invalid = client.post(
        f"/api/v1/admin/recruiters/{recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={
            "plan_id": str(plan.id),
            "starts_at": explicit_start.isoformat(),
            "expires_at": explicit_start.isoformat(),
        },
    )
    assert invalid.status_code == 422


def test_expired_active_is_normalized_then_new_grant_succeeds() -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    _, admin_token = _token(UserRole.ADMIN)
    plan = _plan()
    db = SessionLocal()
    try:
        old = RecruiterSubscription(
            recruiter_id=recruiter.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=datetime.now(timezone.utc) - timedelta(days=31),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            source=SubscriptionSource.ADMIN,
        )
        db.add(old)
        db.commit()
        old_id = old.id
    finally:
        db.close()

    response = client.post(
        f"/api/v1/admin/recruiters/{recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={"plan_id": str(plan.id)},
    )
    assert response.status_code == 200, response.text
    db = SessionLocal()
    try:
        assert db.get(RecruiterSubscription, old_id).status == SubscriptionStatus.EXPIRED
        assert db.scalar(
            select(func.count(RecruiterSubscription.id)).where(
                RecruiterSubscription.recruiter_id == recruiter.id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            )
        ) == 1
    finally:
        db.close()


def test_change_and_idempotent_revoke_preserve_history() -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    _, admin_token = _token(UserRole.ADMIN)
    plan = _plan()
    endpoint = f"/api/v1/admin/recruiters/{recruiter.id}/subscription"
    first = client.post(endpoint, headers=_headers(admin_token), json={"plan_id": str(plan.id)})
    assert first.status_code == 200
    first_id = first.json()["subscription"]["id"]
    second = client.post(endpoint, headers=_headers(admin_token), json={"plan_id": str(plan.id)})
    assert second.status_code == 200
    assert second.json()["subscription"]["id"] != first_id

    db = SessionLocal()
    try:
        assert db.get(RecruiterSubscription, uuid.UUID(first_id)).status == SubscriptionStatus.CANCELLED
        assert db.scalar(
            select(func.count(RecruiterSubscription.id)).where(
                RecruiterSubscription.recruiter_id == recruiter.id
            )
        ) == 2
    finally:
        db.close()

    revoke_url = f"{endpoint}/revoke"
    revoked = client.post(revoke_url, headers=_headers(admin_token))
    repeated = client.post(revoke_url, headers=_headers(admin_token))
    assert revoked.status_code == repeated.status_code == 200
    assert revoked.json()["effective_plan"]["code"] == "FREE"
    assert repeated.json()["subscription"] is None
    db = SessionLocal()
    try:
        assert db.scalar(
            select(func.count(RecruiterSubscription.id)).where(
                RecruiterSubscription.recruiter_id == recruiter.id
            )
        ) == 2
    finally:
        db.close()


def test_used_plan_immutability_mutable_fields_and_deactivation_semantics() -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    other_recruiter, _ = _token(UserRole.RECRUITER)
    _, admin_token = _token(UserRole.ADMIN)
    plan = _plan()
    endpoint = f"/api/v1/admin/recruiters/{recruiter.id}/subscription"
    assert client.post(endpoint, headers=_headers(admin_token), json={"plan_id": str(plan.id)}).status_code == 200

    immutable = client.patch(
        f"{ADMIN_PLANS}/{plan.id}",
        headers=_headers(admin_token),
        json={"duration_days": 60},
    )
    assert immutable.status_code == 409
    updated = client.patch(
        f"{ADMIN_PLANS}/{plan.id}",
        headers=_headers(admin_token),
        json={
            "name": "PRO tháng mới",
            "description": "Updated",
            "price": "120000",
            "is_active": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["price"] == "120000"
    current = client.get(endpoint, headers=_headers(admin_token))
    assert current.status_code == 200
    assert current.json()["effective_plan"]["code"] == "PRO_MONTHLY"
    rejected = client.post(
        f"/api/v1/admin/recruiters/{other_recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={"plan_id": str(plan.id)},
    )
    assert rejected.status_code == 409


def test_free_grant_missing_plan_and_wrong_target_roles_are_rejected() -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    candidate, _ = _token(UserRole.CANDIDATE)
    admin, admin_token = _token(UserRole.ADMIN)
    free = _plan("FREE")
    pro = _plan()
    assert client.post(
        f"/api/v1/admin/recruiters/{recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={"plan_id": str(free.id)},
    ).status_code == 422
    assert client.post(
        f"/api/v1/admin/recruiters/{recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={"plan_id": str(uuid.uuid4())},
    ).status_code == 404
    for wrong_target in (candidate, admin):
        assert client.post(
            f"/api/v1/admin/recruiters/{wrong_target.id}/subscription",
            headers=_headers(admin_token),
            json={"plan_id": str(pro.id)},
        ).status_code == 422
    assert client.get(
        f"/api/v1/admin/recruiters/{uuid.uuid4()}/subscription",
        headers=_headers(admin_token),
    ).status_code == 404


def test_admin_recruiter_list_reports_effective_plans_without_n_plus_one() -> None:
    free_recruiter, _ = _token(UserRole.RECRUITER)
    pro_recruiter, _ = _token(UserRole.RECRUITER)
    expired_recruiter, _ = _token(UserRole.RECRUITER)
    _, admin_token = _token(UserRole.ADMIN)
    plan = _plan()
    assert client.post(
        f"/api/v1/admin/recruiters/{pro_recruiter.id}/subscription",
        headers=_headers(admin_token),
        json={"plan_id": str(plan.id)},
    ).status_code == 200
    db = SessionLocal()
    try:
        db.add(
            RecruiterSubscription(
                recruiter_id=expired_recruiter.id,
                plan_id=plan.id,
                status=SubscriptionStatus.EXPIRED,
                starts_at=datetime.now(timezone.utc) - timedelta(days=31),
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                source=SubscriptionSource.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()

    selects = 0

    def count_selects(conn, cursor, statement, parameters, context, executemany):
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = client.get(
            "/api/v1/admin/recruiters",
            params={"page_size": 100},
            headers=_headers(admin_token),
        )
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)
    assert response.status_code == 200, response.text
    by_id = {item["id"]: item for item in response.json()["items"]}
    assert by_id[str(free_recruiter.id)]["effective_plan"]["code"] == "FREE"
    assert by_id[str(pro_recruiter.id)]["effective_plan"]["code"] == "PRO_MONTHLY"
    assert by_id[str(expired_recruiter.id)]["effective_plan"]["code"] == "FREE"
    assert selects <= 4


def test_grant_rolls_back_old_cancellation_when_new_insert_fails(monkeypatch) -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    plan = _plan()
    db = SessionLocal()
    try:
        service = SubscriptionService(db)
        service.grant_or_change(recruiter.id, SubscriptionGrantRequest(plan_id=plan.id))
        old_id = db.scalar(
            select(RecruiterSubscription.id).where(
                RecruiterSubscription.recruiter_id == recruiter.id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            )
        )

        def fail_insert(subscription):
            raise RuntimeError("forced insert failure")

        monkeypatch.setattr(service.repository, "add_subscription", fail_insert)
        with pytest.raises(RuntimeError, match="forced insert failure"):
            service.grant_or_change(recruiter.id, SubscriptionGrantRequest(plan_id=plan.id))
    finally:
        db.close()

    verify = SessionLocal()
    try:
        assert verify.get(RecruiterSubscription, old_id).status == SubscriptionStatus.ACTIVE
        assert verify.scalar(
            select(func.count(RecruiterSubscription.id)).where(
                RecruiterSubscription.recruiter_id == recruiter.id
            )
        ) == 1
    finally:
        verify.close()


def test_concurrent_grants_leave_exactly_one_active_subscription() -> None:
    recruiter, _ = _token(UserRole.RECRUITER)
    plan = _plan()
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def grant() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=5)
            SubscriptionService(db).grant_or_change(
                recruiter.id, SubscriptionGrantRequest(plan_id=plan.id)
            )
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            db.close()

    threads = [threading.Thread(target=grant) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []

    db = SessionLocal()
    try:
        statuses = list(
            db.scalars(
                select(RecruiterSubscription.status).where(
                    RecruiterSubscription.recruiter_id == recruiter.id
                )
            )
        )
        assert statuses.count(SubscriptionStatus.ACTIVE) == 1
        assert statuses.count(SubscriptionStatus.CANCELLED) == 1
    finally:
        db.close()
