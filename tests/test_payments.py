import hashlib
import hmac
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
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
from app.models.subscription import (
    BillingPeriod,
    RecruiterSubscription,
    SubscriptionPlan,
    SubscriptionSource,
    SubscriptionStatus,
)
from app.models.user import User, UserRole
from app.services.subscription_service import SubscriptionService


client = TestClient(app)
PAYMENT_ORDERS = "/api/v1/recruiter/payment-orders"
WEBHOOK = "/api/v1/payments/sepay/webhook"
TEST_EMAIL_PREFIX = "payment03_"
WEBHOOK_SECRET = "payment-test-secret"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(role: UserRole = UserRole.RECRUITER) -> tuple[User, str]:
    db = SessionLocal()
    try:
        user = User(
            email=f"{TEST_EMAIL_PREFIX}{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name="Payment Test User",
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
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert response.status_code == 200
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


def _create_order(token: str, plan_id: uuid.UUID | None = None) -> dict:
    plan_id = plan_id or _plan().id
    response = client.post(
        PAYMENT_ORDERS,
        headers=_headers(token),
        json={"plan_id": str(plan_id)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _payload(
    transaction_id: str,
    *,
    code: str | None,
    amount: str = "99000",
    transfer_type: str = "in",
    account: str = "0123456789",
    content: str | None = None,
) -> dict:
    return {
        "id": transaction_id,
        "gateway": "TEST",
        "transactionDate": "2026-10-17 12:00:00",
        "accountNumber": account,
        "code": code,
        "content": content if content is not None else (code or "unknown"),
        "transferType": transfer_type,
        "transferAmount": amount,
        "referenceCode": f"REF-{transaction_id}",
    }


def _signed_request(payload: dict, *, timestamp: int | None = None, secret: str = WEBHOOK_SECRET):
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(
        secret.encode("utf-8"), str(timestamp).encode("ascii") + b"." + raw, hashlib.sha256
    ).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-SePay-Timestamp": str(timestamp),
        "X-SePay-Signature": f"sha256={digest}",
    }


def _webhook(payload: dict):
    raw, headers = _signed_request(payload)
    return client.post(WEBHOOK, content=raw, headers=headers)


def _cleanup() -> None:
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like(f"{TEST_EMAIL_PREFIX}%"))))
        if user_ids:
            order_ids = list(
                db.scalars(select(PaymentOrder.id).where(PaymentOrder.recruiter_id.in_(user_ids)))
            )
            if order_ids:
                db.query(PaymentTransaction).filter(
                    PaymentTransaction.payment_order_id.in_(order_ids)
                ).delete(synchronize_session=False)
                db.query(PaymentOrder).filter(PaymentOrder.id.in_(order_ids)).delete(
                    synchronize_session=False
                )
            db.query(RecruiterSubscription).filter(
                RecruiterSubscription.recruiter_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.query(PaymentTransaction).filter(
            PaymentTransaction.provider_transaction_id.like("PAYTEST-%")
        ).delete(synchronize_session=False)
        db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code.like("PAYTEST_%")
        ).delete(synchronize_session=False)
        db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "PRO_MONTHLY").update(
            {
                SubscriptionPlan.name: "PRO thang",
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
def payment_environment(monkeypatch):
    monkeypatch.setattr(settings, "SEPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "SEPAY_BANK_NAME", "Test Bank")
    monkeypatch.setattr(settings, "SEPAY_BANK_BIN", "970436")
    monkeypatch.setattr(settings, "SEPAY_BANK_ACCOUNT", "0123456789")
    monkeypatch.setattr(settings, "SEPAY_ACCOUNT_NAME", "GJOB TEST")
    monkeypatch.setattr(settings, "SEPAY_PAYMENT_CODE_PREFIX", "GJOB")
    monkeypatch.setattr(settings, "PAYMENT_ORDER_TTL_MINUTES", 30)
    _cleanup()
    yield
    _cleanup()


def test_create_order_is_server_authoritative_reuses_pending_and_enforces_ownership() -> None:
    recruiter, token = _create_user()
    other, other_token = _create_user()
    plan = _plan()
    before = datetime.now(timezone.utc)
    response = client.post(
        PAYMENT_ORDERS,
        headers=_headers(token),
        json={"plan_id": str(plan.id), "amount": "1"},
    )
    assert response.status_code == 422

    order = _create_order(token, plan.id)
    assert order["amount"] == "99000"
    assert order["currency"] == "VND"
    assert order["plan"]["billing_period"] == "MONTHLY"
    assert order["plan"]["duration_days"] == 30
    assert order["payment_code"].startswith("GJOB")
    assert order["transfer_content"] == order["payment_code"]
    assert "amount=99000" in order["qr"]["image_url"]
    assert f"addInfo={order['payment_code']}" in order["qr"]["image_url"]
    expires = datetime.fromisoformat(order["expires_at"])
    assert before + timedelta(minutes=29) < expires < before + timedelta(minutes=31)

    reused = _create_order(token, plan.id)
    assert reused["id"] == order["id"]
    assert client.get(
        f"{PAYMENT_ORDERS}/{order['id']}", headers=_headers(other_token)
    ).status_code == 404
    assert client.get(f"{PAYMENT_ORDERS}/{order['id']}").status_code == 401

    _, candidate_token = _create_user(UserRole.CANDIDATE)
    assert client.post(
        PAYMENT_ORDERS,
        headers=_headers(candidate_token),
        json={"plan_id": str(plan.id)},
    ).status_code == 403
    assert client.get(
        f"{PAYMENT_ORDERS}/{order['id']}", headers=_headers(candidate_token)
    ).status_code == 403
    assert recruiter.id != other.id


def test_recruiter_can_cancel_only_an_owned_pending_order() -> None:
    _, token = _create_user()
    _, other_token = _create_user()
    order = _create_order(token)

    assert client.post(
        f"{PAYMENT_ORDERS}/{order['id']}/cancel", headers=_headers(other_token)
    ).status_code == 404
    assert client.post(f"{PAYMENT_ORDERS}/{order['id']}/cancel").status_code == 401
    _, candidate_token = _create_user(UserRole.CANDIDATE)
    assert client.post(
        f"{PAYMENT_ORDERS}/{order['id']}/cancel", headers=_headers(candidate_token)
    ).status_code == 403

    cancelled = client.post(
        f"{PAYMENT_ORDERS}/{order['id']}/cancel", headers=_headers(token)
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    repeated = client.post(
        f"{PAYMENT_ORDERS}/{order['id']}/cancel", headers=_headers(token)
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "CANCELLED"

    replacement = _create_order(token)
    assert replacement["id"] != order["id"]
    assert replacement["payment_code"] != order["payment_code"]
    with SessionLocal() as db:
        persisted = db.get(PaymentOrder, uuid.UUID(order["id"]))
        assert persisted is not None and persisted.status == PaymentOrderStatus.CANCELLED


def test_paid_or_expired_order_cannot_be_cancelled() -> None:
    _, token = _create_user()
    paid = _create_order(token)
    assert _webhook(_payload("PAYTEST-PAID-CANCEL", code=paid["payment_code"])).status_code == 200
    paid_cancel = client.post(
        f"{PAYMENT_ORDERS}/{paid['id']}/cancel", headers=_headers(token)
    )
    assert paid_cancel.status_code == 409

    expired = _create_order(token)
    with SessionLocal() as db:
        db.query(PaymentOrder).filter(PaymentOrder.id == uuid.UUID(expired["id"])).update(
            {PaymentOrder.expires_at: datetime.now(timezone.utc) - timedelta(seconds=1)},
            synchronize_session=False,
        )
        db.commit()
    expired_cancel = client.post(
        f"{PAYMENT_ORDERS}/{expired['id']}/cancel", headers=_headers(token)
    )
    assert expired_cancel.status_code == 409
    assert expired_cancel.json()["detail"]["status"] == "EXPIRED"
    with SessionLocal() as db:
        persisted = db.get(PaymentOrder, uuid.UUID(expired["id"]))
        assert persisted is not None and persisted.status == PaymentOrderStatus.EXPIRED


def test_free_inactive_and_cross_plan_orders_are_rejected() -> None:
    recruiter, token = _create_user()
    free = _plan("FREE")
    assert client.post(
        PAYMENT_ORDERS, headers=_headers(token), json={"plan_id": str(free.id)}
    ).status_code == 422

    pro = _plan()
    db = SessionLocal()
    try:
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == pro.id).update(
            {SubscriptionPlan.is_active: False}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    assert client.post(
        PAYMENT_ORDERS, headers=_headers(token), json={"plan_id": str(pro.id)}
    ).status_code == 409

    db = SessionLocal()
    try:
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == pro.id).update(
            {SubscriptionPlan.is_active: True}, synchronize_session=False
        )
        other_plan = SubscriptionPlan(
            code="PAYTEST_OTHER",
            name="Other paid plan",
            price=Decimal("120000"),
            currency="VND",
            billing_period=BillingPeriod.MONTHLY,
            duration_days=30,
            is_active=True,
        )
        db.add(other_plan)
        db.flush()
        db.add(
            RecruiterSubscription(
                recruiter_id=recruiter.id,
                plan_id=other_plan.id,
                status=SubscriptionStatus.ACTIVE,
                starts_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=10),
                source=SubscriptionSource.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()
    assert client.post(
        PAYMENT_ORDERS, headers=_headers(token), json={"plan_id": str(pro.id)}
    ).status_code == 409


def test_hmac_failures_are_rejected_without_state_change() -> None:
    _, token = _create_user()
    order = _create_order(token)
    payload = _payload("PAYTEST-HMAC", code=order["payment_code"])
    raw, headers = _signed_request(payload)

    assert client.post(WEBHOOK, content=raw, headers={"Content-Type": "application/json"}).status_code == 401
    bad = {**headers, "X-SePay-Signature": "sha256=bad"}
    assert client.post(WEBHOOK, content=raw, headers=bad).status_code == 401
    stale_raw, stale_headers = _signed_request(payload, timestamp=int(time.time()) - 301)
    assert client.post(WEBHOOK, content=stale_raw, headers=stale_headers).status_code == 401
    malformed = {**headers, "X-SePay-Timestamp": "not-a-number"}
    assert client.post(WEBHOOK, content=raw, headers=malformed).status_code == 401

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count(PaymentTransaction.id))) == 0
        persisted = db.get(PaymentOrder, uuid.UUID(order["id"]))
        assert persisted is not None and persisted.status == PaymentOrderStatus.PENDING
    finally:
        db.close()


def test_valid_hmac_with_malformed_payload_returns_400_without_writes() -> None:
    raw, headers = _signed_request({"id": "PAYTEST-MALFORMED"})
    response = client.post(WEBHOOK, content=raw, headers=headers)
    assert response.status_code == 400
    db = SessionLocal()
    try:
        assert db.scalar(
            select(func.count(PaymentTransaction.id)).where(
                PaymentTransaction.provider_transaction_id == "PAYTEST-MALFORMED"
            )
        ) == 0
    finally:
        db.close()


def test_full_snapshot_valid_webhook_activates_subscription_and_entitlements() -> None:
    recruiter, token = _create_user()
    order = _create_order(token)
    plan = _plan()
    db = SessionLocal()
    try:
        db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan.id).update(
            {SubscriptionPlan.price: Decimal("129000"), SubscriptionPlan.duration_days: 45},
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()

    response = _webhook(_payload("PAYTEST-APPLY", code=order["payment_code"]))
    assert response.status_code == 200 and response.json() == {"success": True}
    current = client.get("/api/v1/recruiter/subscription", headers=_headers(token))
    assert current.status_code == 200
    assert current.json()["effective_plan"]["code"] == "PRO_MONTHLY"
    assert current.json()["subscription"]["source"] == "PAYMENT"
    assert current.json()["entitlements"]["AI_CANDIDATE_RANKING"] is True

    db = SessionLocal()
    try:
        persisted = db.get(PaymentOrder, uuid.UUID(order["id"]))
        assert persisted is not None
        assert persisted.status == PaymentOrderStatus.PAID
        assert persisted.plan_code_snapshot == "PRO_MONTHLY"
        assert persisted.plan_name_snapshot == order["plan"]["name"]
        assert persisted.amount == Decimal("99000")
        assert persisted.currency == "VND"
        assert persisted.billing_period_snapshot == "MONTHLY"
        assert persisted.duration_days_snapshot == 30
        subscription = db.scalar(
            select(RecruiterSubscription).where(
                RecruiterSubscription.recruiter_id == recruiter.id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        assert subscription is not None and subscription.expires_at is not None
        assert timedelta(days=29, hours=23) < subscription.expires_at - subscription.starts_at < timedelta(days=30, minutes=1)
    finally:
        db.close()


@pytest.mark.parametrize(
    ("transaction_id", "overrides", "expected"),
    [
        ("PAYTEST-OUT", {"transfer_type": "out"}, PaymentDisposition.OUTGOING_IGNORED),
        ("PAYTEST-ACCOUNT", {"account": "999"}, PaymentDisposition.ACCOUNT_MISMATCH),
        ("PAYTEST-AMOUNT", {"amount": "98000"}, PaymentDisposition.AMOUNT_MISMATCH),
    ],
)
def test_business_non_application_dispositions_acknowledge_success(
    transaction_id: str, overrides: dict, expected: PaymentDisposition
) -> None:
    _, token = _create_user()
    order = _create_order(token)
    response = _webhook(_payload(transaction_id, code=order["payment_code"], **overrides))
    assert response.status_code == 200 and response.json() == {"success": True}
    db = SessionLocal()
    try:
        transaction = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider_transaction_id == transaction_id
            )
        )
        assert transaction is not None and transaction.disposition == expected
        persisted = db.get(PaymentOrder, uuid.UUID(order["id"]))
        assert persisted is not None and persisted.status == PaymentOrderStatus.PENDING
    finally:
        db.close()


def test_unmatched_code_priority_and_exact_content_boundary() -> None:
    _, token = _create_user()
    order = _create_order(token)
    explicit_unknown = _payload(
        "PAYTEST-CODE-PRIORITY",
        code="GJOB000000000000",
        content=order["payment_code"],
    )
    assert _webhook(explicit_unknown).status_code == 200
    collision = _payload(
        "PAYTEST-COLLISION",
        code="",
        content=f"XX{order['payment_code']}YY",
    )
    assert _webhook(collision).status_code == 200
    exact = _payload(
        "PAYTEST-FALLBACK",
        code="",
        content=f"Thanh toan {order['payment_code']} ngay",
    )
    assert _webhook(exact).status_code == 200

    db = SessionLocal()
    try:
        dispositions = {
            row.provider_transaction_id: row.disposition
            for row in db.scalars(
                select(PaymentTransaction).where(
                    PaymentTransaction.provider_transaction_id.in_(
                        ["PAYTEST-CODE-PRIORITY", "PAYTEST-COLLISION", "PAYTEST-FALLBACK"]
                    )
                )
            )
        }
        assert dispositions["PAYTEST-CODE-PRIORITY"] == PaymentDisposition.UNMATCHED
        assert dispositions["PAYTEST-COLLISION"] == PaymentDisposition.UNMATCHED
        assert dispositions["PAYTEST-FALLBACK"] == PaymentDisposition.APPLIED
    finally:
        db.close()


def test_payload_adapter_persists_exact_provider_transaction_fields() -> None:
    _, token = _create_user()
    order = _create_order(token)
    payload = _payload(
        "PAYTEST-MAPPING",
        code="GJOB000000000000",
        amount="12345",
        account="000111222",
        content="mapping content",
    )
    payload["transactionDate"] = "2026-10-17 13:14:15"
    payload["referenceCode"] = "MAPPING-REFERENCE"
    assert _webhook(payload).status_code == 200

    db = SessionLocal()
    try:
        transaction = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider_transaction_id == "PAYTEST-MAPPING"
            )
        )
        assert transaction is not None
        assert transaction.provider == PaymentProvider.SEPAY
        assert transaction.payment_order_id is None
        assert transaction.amount == Decimal("12345")
        assert transaction.transaction_date.isoformat() == "2026-10-17T06:14:15+00:00"
        assert transaction.reference_code == "MAPPING-REFERENCE"
        assert transaction.content == "mapping content"
        assert transaction.destination_account == "000111222"
        assert transaction.disposition == PaymentDisposition.ACCOUNT_MISMATCH
        persisted = db.get(PaymentOrder, uuid.UUID(order["id"]))
        assert persisted is not None and persisted.status == PaymentOrderStatus.PENDING
    finally:
        db.close()


def test_lazy_expiry_and_cancelled_webhook_dispositions() -> None:
    _, token = _create_user()
    expired = _create_order(token)
    db = SessionLocal()
    try:
        db.query(PaymentOrder).filter(PaymentOrder.id == uuid.UUID(expired["id"])).update(
            {PaymentOrder.expires_at: datetime.now(timezone.utc) - timedelta(seconds=1)},
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()
    expired_response = _webhook(
        _payload("PAYTEST-EXPIRED", code=expired["payment_code"])
    )
    assert expired_response.status_code == 200
    read = client.get(f"{PAYMENT_ORDERS}/{expired['id']}", headers=_headers(token))
    assert read.status_code == 200 and read.json()["status"] == "EXPIRED"
    fresh = _create_order(token)
    assert fresh["id"] != expired["id"]
    assert fresh["payment_code"] != expired["payment_code"]
    db = SessionLocal()
    try:
        db.query(PaymentOrder).filter(PaymentOrder.id == uuid.UUID(fresh["id"])).update(
            {PaymentOrder.status: PaymentOrderStatus.CANCELLED}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    response = _webhook(_payload("PAYTEST-CANCEL", code=fresh["payment_code"]))
    assert response.status_code == 200
    db = SessionLocal()
    try:
        expired_transaction = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider_transaction_id == "PAYTEST-EXPIRED"
            )
        )
        assert expired_transaction is not None
        assert expired_transaction.disposition == PaymentDisposition.ORDER_EXPIRED
        transaction = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider_transaction_id == "PAYTEST-CANCEL"
            )
        )
        assert transaction is not None and transaction.disposition == PaymentDisposition.ORDER_CANCELLED
    finally:
        db.close()


def test_same_plan_renewal_and_duplicate_webhook_extend_exactly_once() -> None:
    recruiter, token = _create_user()
    first = _create_order(token)
    assert _webhook(_payload("PAYTEST-FIRST", code=first["payment_code"])).status_code == 200
    db = SessionLocal()
    try:
        initial = db.scalar(
            select(RecruiterSubscription).where(
                RecruiterSubscription.recruiter_id == recruiter.id,
                RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        assert initial is not None and initial.expires_at is not None
        initial_expiry = initial.expires_at
    finally:
        db.close()

    second = _create_order(token)
    payload = _payload("PAYTEST-RENEW", code=second["payment_code"])
    assert _webhook(payload).status_code == 200
    assert _webhook(payload).status_code == 200
    db = SessionLocal()
    try:
        active = list(
            db.scalars(
                select(RecruiterSubscription).where(
                    RecruiterSubscription.recruiter_id == recruiter.id,
                    RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
                )
            )
        )
        assert len(active) == 1
        assert active[0].expires_at == initial_expiry + timedelta(days=30)
        assert db.scalar(
            select(func.count(PaymentTransaction.id)).where(
                PaymentTransaction.provider_transaction_id == "PAYTEST-RENEW"
            )
        ) == 1
    finally:
        db.close()


def test_atomic_rollback_when_subscription_mutation_fails(monkeypatch) -> None:
    _, token = _create_user()
    order = _create_order(token)

    def fail_after_payment_mutation(*args, **kwargs):
        raise RuntimeError("synthetic subscription failure")

    monkeypatch.setattr(SubscriptionService, "apply_payment_no_commit", fail_after_payment_mutation)
    with pytest.raises(RuntimeError, match="synthetic subscription failure"):
        _webhook(_payload("PAYTEST-ROLLBACK", code=order["payment_code"]))

    db = SessionLocal()
    try:
        assert db.scalar(
            select(func.count(PaymentTransaction.id)).where(
                PaymentTransaction.provider_transaction_id == "PAYTEST-ROLLBACK"
            )
        ) == 0
        persisted = db.get(PaymentOrder, uuid.UUID(order["id"]))
        assert persisted is not None and persisted.status == PaymentOrderStatus.PENDING
    finally:
        db.close()


def test_concurrent_duplicate_webhook_applies_once() -> None:
    recruiter, token = _create_user()
    order = _create_order(token)
    payload = _payload("PAYTEST-CONCURRENT", code=order["payment_code"])
    raw, headers = _signed_request(payload)
    barrier = threading.Barrier(2)
    results: list[int] = []

    def deliver() -> None:
        with TestClient(app) as thread_client:
            barrier.wait()
            results.append(thread_client.post(WEBHOOK, content=raw, headers=headers).status_code)

    threads = [threading.Thread(target=deliver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert results == [200, 200]

    db = SessionLocal()
    try:
        assert db.scalar(
            select(func.count(PaymentTransaction.id)).where(
                PaymentTransaction.provider == PaymentProvider.SEPAY,
                PaymentTransaction.provider_transaction_id == "PAYTEST-CONCURRENT",
            )
        ) == 1
        active = list(
            db.scalars(
                select(RecruiterSubscription).where(
                    RecruiterSubscription.recruiter_id == recruiter.id,
                    RecruiterSubscription.status == SubscriptionStatus.ACTIVE,
                )
            )
        )
        assert len(active) == 1
    finally:
        db.close()
