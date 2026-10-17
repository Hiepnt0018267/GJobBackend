import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.payment import (
    PaymentDisposition,
    PaymentOrder,
    PaymentOrderStatus,
    PaymentProvider,
    PaymentTransaction,
)
from app.models.subscription import SubscriptionPlan
from app.models.user import User, UserRole


client = TestClient(app)
PREFIX = "adminpay04_"


def _create_user(role: UserRole) -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"{PREFIX}{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name=f"Admin payment {role.value}",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
    finally:
        db.close()
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "password123"}
    )
    assert response.status_code == 200
    return user, response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed(recruiter: User) -> dict[str, uuid.UUID]:
    db = SessionLocal()
    try:
        plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == "PRO_MONTHLY"))
        assert plan is not None
        now = datetime.now(timezone.utc)
        paid = PaymentOrder(
            recruiter_id=recruiter.id,
            plan_id=plan.id,
            plan_code_snapshot=plan.code,
            plan_name_snapshot=plan.name,
            amount=Decimal("99000"),
            currency="VND",
            billing_period_snapshot="MONTHLY",
            duration_days_snapshot=30,
            payment_code=f"ADM{uuid.uuid4().hex[:12].upper()}",
            status=PaymentOrderStatus.PAID,
            expires_at=now + timedelta(minutes=30),
            paid_at=now,
            created_at=now - timedelta(days=1),
        )
        pending = PaymentOrder(
            recruiter_id=recruiter.id,
            plan_id=plan.id,
            plan_code_snapshot=plan.code,
            plan_name_snapshot=plan.name,
            amount=Decimal("99000"),
            currency="VND",
            billing_period_snapshot="MONTHLY",
            duration_days_snapshot=30,
            payment_code=f"ADM{uuid.uuid4().hex[:12].upper()}",
            status=PaymentOrderStatus.PENDING,
            expires_at=now + timedelta(minutes=30),
        )
        stale = PaymentOrder(
            recruiter_id=recruiter.id,
            plan_id=plan.id,
            plan_code_snapshot=plan.code,
            plan_name_snapshot=plan.name,
            amount=Decimal("99000"),
            currency="VND",
            billing_period_snapshot="MONTHLY",
            duration_days_snapshot=30,
            payment_code=f"ADM{uuid.uuid4().hex[:12].upper()}",
            status=PaymentOrderStatus.PENDING,
            expires_at=now - timedelta(minutes=1),
        )
        db.add_all([paid, pending, stale])
        db.flush()
        applied = PaymentTransaction(
            payment_order_id=paid.id,
            provider=PaymentProvider.SEPAY,
            provider_transaction_id=f"{PREFIX}APPLIED",
            amount=Decimal("99000"),
            transaction_date=now,
            reference_code="REF-APPLIED",
            content=paid.payment_code,
            destination_account="0123456789",
            disposition=PaymentDisposition.APPLIED,
        )
        mismatch = PaymentTransaction(
            payment_order_id=paid.id,
            provider=PaymentProvider.SEPAY,
            provider_transaction_id=f"{PREFIX}MISMATCH",
            amount=Decimal("98000"),
            transaction_date=now - timedelta(minutes=1),
            reference_code="REF-MISMATCH",
            content=paid.payment_code,
            destination_account="0123456789",
            disposition=PaymentDisposition.AMOUNT_MISMATCH,
        )
        unmatched = PaymentTransaction(
            payment_order_id=None,
            provider=PaymentProvider.SEPAY,
            provider_transaction_id=f"{PREFIX}UNMATCHED",
            amount=Decimal("120000"),
            transaction_date=now - timedelta(minutes=2),
            reference_code="REF-UNMATCHED",
            content="UNKNOWN PAYMENT",
            destination_account="0123456789",
            disposition=PaymentDisposition.UNMATCHED,
        )
        db.add_all([applied, mismatch, unmatched])
        db.commit()
        return {
            "paid": paid.id,
            "pending": pending.id,
            "stale": stale.id,
            "applied": applied.id,
        }
    finally:
        db.close()


def _cleanup() -> None:
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like(f"{PREFIX}%"))))
        order_ids = list(
            db.scalars(select(PaymentOrder.id).where(PaymentOrder.recruiter_id.in_(user_ids)))
        ) if user_ids else []
        db.query(PaymentTransaction).filter(
            PaymentTransaction.provider_transaction_id.like(f"{PREFIX}%")
        ).delete(synchronize_session=False)
        if order_ids:
            db.query(PaymentTransaction).filter(
                PaymentTransaction.payment_order_id.in_(order_ids)
            ).delete(synchronize_session=False)
        if order_ids:
            db.query(PaymentOrder).filter(PaymentOrder.id.in_(order_ids)).delete(
                synchronize_session=False
            )
        if user_ids:
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_admin_payment_rows():
    _cleanup()
    yield
    _cleanup()


def test_admin_payment_history_is_admin_only_and_returns_decimal_strings() -> None:
    recruiter, recruiter_token = _create_user(UserRole.RECRUITER)
    _, admin_token = _create_user(UserRole.ADMIN)
    _seed(recruiter)
    path = "/api/v1/admin/payment-transactions"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=_headers(recruiter_token)).status_code == 403
    response = client.get(
        path, params={"search": PREFIX, "page": 1, "page_size": 2}, headers=_headers(admin_token)
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 2
    assert all(isinstance(item["amount"], str) for item in payload["items"])


def test_summary_counts_only_applied_revenue_and_active_pending_orders() -> None:
    recruiter, _ = _create_user(UserRole.RECRUITER)
    _, admin_token = _create_user(UserRole.ADMIN)
    _seed(recruiter)
    response = client.get(
        "/api/v1/admin/payments/summary",
        params={"plan_code": "PRO_MONTHLY"},
        headers=_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "successful_transactions": 1,
        "revenue": "99000",
        "needs_review": 1,
        "pending_orders": 1,
        "paid_orders": 1,
    }


def test_stale_pending_order_is_derived_as_expired_without_database_write() -> None:
    recruiter, _ = _create_user(UserRole.RECRUITER)
    _, admin_token = _create_user(UserRole.ADMIN)
    ids = _seed(recruiter)
    response = client.get(
        "/api/v1/admin/payment-orders",
        params={"order_status": "EXPIRED"},
        headers=_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(ids["stale"])
    assert response.json()["items"][0]["status"] == "EXPIRED"
    db = SessionLocal()
    try:
        assert db.get(PaymentOrder, ids["stale"]).status == PaymentOrderStatus.PENDING
    finally:
        db.close()


def test_payment_details_filters_and_date_validation() -> None:
    recruiter, _ = _create_user(UserRole.RECRUITER)
    _, admin_token = _create_user(UserRole.ADMIN)
    ids = _seed(recruiter)
    transaction = client.get(
        f"/api/v1/admin/payment-transactions/{ids['applied']}",
        headers=_headers(admin_token),
    )
    assert transaction.status_code == 200
    assert transaction.json()["order"]["recruiter"]["email"] == recruiter.email
    order = client.get(
        f"/api/v1/admin/payment-orders/{ids['paid']}", headers=_headers(admin_token)
    )
    assert order.status_code == 200
    assert len(order.json()["transactions"]) == 2
    assert client.get(
        "/api/v1/admin/payment-transactions",
        params={"date_from": "2026-01-01T00:00:00"},
        headers=_headers(admin_token),
    ).status_code == 422
    assert client.get(
        "/api/v1/admin/payment-orders",
        params={"date_from": "2026-10-18T00:00:00Z", "date_to": "2026-10-17T00:00:00Z"},
        headers=_headers(admin_token),
    ).status_code == 422
    missing = uuid.uuid4()
    assert client.get(
        f"/api/v1/admin/payment-orders/{missing}", headers=_headers(admin_token)
    ).status_code == 404
