import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.subscription import (
    RecruiterSubscription,
    SubscriptionPlan,
    SubscriptionSource,
    SubscriptionStatus,
)
from app.models.user import User, UserRole
from app.schemas.subscription import RecruiterFeature
from app.services.applicant_ranking_service import ApplicantRankingService
from app.services.cv_job_match_service import CVJobMatchService
from app.services.recruiter_entitlement_service import RecruiterEntitlementService


client = TestClient(app)
PREFIX = "mon02_"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_and_token(role: UserRole) -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"{PREFIX}{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name="Entitlement test",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
    finally:
        db.close()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert login.status_code == 200
    return user, login.json()["access_token"]


def _grant(recruiter_id: uuid.UUID, plan_code: str, *, expired: bool = False) -> None:
    db = SessionLocal()
    try:
        plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code))
        assert plan is not None
        now = datetime.now(timezone.utc)
        db.add(
            RecruiterSubscription(
                recruiter_id=recruiter_id,
                plan_id=plan.id,
                status=SubscriptionStatus.ACTIVE,
                starts_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1) if expired else now + timedelta(days=1),
                source=SubscriptionSource.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_entitlement_rows():
    yield
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like(f"{PREFIX}%"))))
        if user_ids:
            db.query(RecruiterSubscription).filter(
                RecruiterSubscription.recruiter_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code.like("TEST_ENTITLEMENT_%")
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_current_subscription_and_catalog_expose_authoritative_features() -> None:
    recruiter, token = _user_and_token(UserRole.RECRUITER)
    current = client.get("/api/v1/recruiter/subscription", headers=_headers(token))
    assert current.status_code == 200
    assert current.json()["effective_plan"]["code"] == "FREE"
    assert current.json()["entitlements"] == {
        "AI_CANDIDATE_RANKING": False,
        "DETAILED_CV_JD_MATCH": False,
    }

    catalog = client.get("/api/v1/recruiter/subscription-plans", headers=_headers(token))
    assert catalog.status_code == 200
    by_code = {plan["code"]: plan for plan in catalog.json()}
    assert by_code["FREE"]["price"] == "0"
    assert all(not feature["included"] for feature in by_code["FREE"]["features"])
    assert all(feature["label"] for feature in by_code["PRO_MONTHLY"]["features"])
    assert all(feature["included"] for feature in by_code["PRO_MONTHLY"]["features"])

    _grant(recruiter.id, "PRO_MONTHLY")
    paid = client.get("/api/v1/recruiter/subscription", headers=_headers(token))
    assert paid.status_code == 200
    assert paid.json()["effective_plan"]["code"] == "PRO_MONTHLY"
    assert all(paid.json()["entitlements"].values())


def test_unknown_and_expired_plans_fail_closed() -> None:
    recruiter, token = _user_and_token(UserRole.RECRUITER)
    db = SessionLocal()
    try:
        template = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == "PRO_MONTHLY"))
        assert template is not None
        unknown = SubscriptionPlan(
            code="TEST_ENTITLEMENT_CUSTOM",
            name="Custom",
            price=template.price,
            currency=template.currency,
            billing_period=template.billing_period,
            duration_days=template.duration_days,
            is_active=True,
        )
        db.add(unknown)
        db.commit()
    finally:
        db.close()
    _grant(recruiter.id, "TEST_ENTITLEMENT_CUSTOM")
    response = client.get("/api/v1/recruiter/subscription", headers=_headers(token))
    assert response.status_code == 200
    assert not any(response.json()["entitlements"].values())

    assert not any(
        RecruiterEntitlementService.for_plan_code("FUTURE_PLAN").values()
    )

    db = SessionLocal()
    try:
        db.query(RecruiterSubscription).filter(
            RecruiterSubscription.recruiter_id == recruiter.id
        ).update({RecruiterSubscription.status: SubscriptionStatus.CANCELLED})
        db.commit()
    finally:
        db.close()
    _grant(recruiter.id, "PRO_MONTHLY", expired=True)
    expired = client.get("/api/v1/recruiter/subscription", headers=_headers(token))
    assert expired.status_code == 200
    assert expired.json()["effective_plan"]["code"] == "FREE"
    assert not any(expired.json()["entitlements"].values())


def test_free_gates_ai_before_ranking_or_matching(monkeypatch) -> None:
    _, token = _user_and_token(UserRole.RECRUITER)

    def forbidden_ranking(*args, **kwargs):
        raise AssertionError("ranking service must not run for FREE")

    async def forbidden_match(*args, **kwargs):
        raise AssertionError("match service must not run for FREE")

    monkeypatch.setattr(ApplicantRankingService, "list", forbidden_ranking)
    monkeypatch.setattr(CVJobMatchService, "match_for_recruiter_application", forbidden_match)

    ranking = client.get(
        "/api/v1/recruiters/applications",
        params={"sort": "ai_match"},
        headers=_headers(token),
    )
    matching = client.post(
        f"/api/v1/recruiters/applications/{uuid.uuid4()}/match",
        headers=_headers(token),
    )
    for response, feature in (
        (ranking, RecruiterFeature.AI_CANDIDATE_RANKING.value),
        (matching, RecruiterFeature.DETAILED_CV_JD_MATCH.value),
    ):
        assert response.status_code == 403
        assert response.json()["detail"] == {
            "code": "FEATURE_NOT_INCLUDED",
            "feature": feature,
            "message": "Tính năng này không có trong gói hiện tại.",
        }


def test_candidate_match_contract_is_not_plan_gated(monkeypatch) -> None:
    _, candidate_token = _user_and_token(UserRole.CANDIDATE)
    response = client.post(
        f"/api/v1/candidate/jobs/{uuid.uuid4()}/match",
        json={"cv_id": str(uuid.uuid4())},
        headers=_headers(candidate_token),
    )
    assert response.status_code == 404
