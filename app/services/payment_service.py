import re
import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote, urlencode

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import (
    PaymentDisposition,
    PaymentOrder,
    PaymentOrderStatus,
    PaymentProvider,
    PaymentTransaction,
)
from app.models.subscription import BillingPeriod, SubscriptionStatus
from app.models.user import User, UserRole
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import (
    PaymentBankResponse,
    PaymentOrderResponse,
    PaymentPlanSnapshotResponse,
    PaymentQrResponse,
    SePayWebhookPayload,
)
from app.services.subscription_service import PaymentPlanConflictError, SubscriptionService


@dataclass(frozen=True)
class PaymentBankConfiguration:
    bank_name: str
    bank_bin: str
    account_number: str
    account_name: str


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PaymentRepository(db)

    def create_order(self, recruiter: User, plan_id: uuid.UUID) -> PaymentOrderResponse:
        bank = self._bank_configuration()
        now = datetime.now(timezone.utc)
        try:
            locked_recruiter = self.repository.get_recruiter_for_update(recruiter.id)
            if locked_recruiter is None or locked_recruiter.role != UserRole.RECRUITER:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found.")

            plan = self.repository.get_plan_for_update(plan_id)
            if plan is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found.")
            if plan.code == "FREE":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="The FREE plan cannot be purchased.",
                )
            if not plan.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This subscription plan is inactive.",
                )
            if (
                plan.price <= Decimal("0")
                or plan.currency != "VND"
                or plan.billing_period != BillingPeriod.MONTHLY
                or plan.duration_days is None
                or plan.duration_days <= 0
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="This plan is not purchasable through the payment flow.",
                )

            for subscription in self.repository.active_subscriptions_for_update(recruiter.id):
                if subscription.expires_at is not None and subscription.expires_at <= now:
                    subscription.status = SubscriptionStatus.EXPIRED
                    subscription.updated_at = now
                    continue
                if subscription.plan_id != plan.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A different paid plan is already active.",
                    )
                if subscription.expires_at is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A perpetual subscription cannot be extended by this payment flow.",
                    )

            reusable: PaymentOrder | None = None
            for existing in self.repository.pending_orders_for_update(recruiter.id, plan.id):
                if existing.expires_at <= now:
                    existing.status = PaymentOrderStatus.EXPIRED
                    existing.updated_at = now
                elif reusable is None:
                    reusable = existing
            if reusable is not None:
                self.repository.commit()
                self.repository.refresh(reusable)
                return self._response(reusable, bank)

            payment_code = self._new_payment_code()
            order = PaymentOrder(
                recruiter_id=recruiter.id,
                plan_id=plan.id,
                plan_code_snapshot=plan.code,
                plan_name_snapshot=plan.name,
                amount=plan.price,
                currency=plan.currency,
                billing_period_snapshot=(
                    plan.billing_period.value
                    if isinstance(plan.billing_period, BillingPeriod)
                    else str(plan.billing_period)
                ),
                duration_days_snapshot=plan.duration_days,
                payment_code=payment_code,
                status=PaymentOrderStatus.PENDING,
                expires_at=now + timedelta(minutes=settings.PAYMENT_ORDER_TTL_MINUTES),
                created_at=now,
                updated_at=now,
            )
            self.repository.add(order)
            self.repository.flush()
            self.repository.commit()
            self.repository.refresh(order)
            return self._response(order, bank)
        except HTTPException:
            self.repository.rollback()
            raise
        except IntegrityError as exc:
            self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A payment order could not be created safely. Please retry.",
            ) from exc
        except Exception:
            self.repository.rollback()
            raise

    def get_order(self, recruiter: User, order_id: uuid.UUID) -> PaymentOrderResponse:
        bank = self._bank_configuration()
        now = datetime.now(timezone.utc)
        try:
            order = self.repository.get_owned_order_for_update(order_id, recruiter.id)
            if order is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found.")
            if order.status == PaymentOrderStatus.PENDING and order.expires_at <= now:
                order.status = PaymentOrderStatus.EXPIRED
                order.updated_at = now
                self.repository.commit()
                self.repository.refresh(order)
            return self._response(order, bank)
        except HTTPException:
            self.repository.rollback()
            raise
        except Exception:
            self.repository.rollback()
            raise

    def cancel_order(self, recruiter: User, order_id: uuid.UUID) -> PaymentOrderResponse:
        bank = self._bank_configuration()
        now = datetime.now(timezone.utc)
        try:
            order = self.repository.get_owned_order_for_update(order_id, recruiter.id)
            if order is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found.")
            if order.status == PaymentOrderStatus.CANCELLED:
                return self._response(order, bank)
            if order.status == PaymentOrderStatus.PENDING and order.expires_at <= now:
                order.status = PaymentOrderStatus.EXPIRED
                order.updated_at = now
                self.repository.commit()
                self.repository.refresh(order)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "PAYMENT_ORDER_NOT_PENDING", "status": PaymentOrderStatus.EXPIRED.value},
                )
            if order.status != PaymentOrderStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "PAYMENT_ORDER_NOT_PENDING",
                        "status": PaymentOrderStatus(order.status).value,
                    },
                )

            order.status = PaymentOrderStatus.CANCELLED
            order.updated_at = now
            self.repository.commit()
            self.repository.refresh(order)
            return self._response(order, bank)
        except HTTPException:
            self.repository.rollback()
            raise
        except Exception:
            self.repository.rollback()
            raise

    def process_sepay_webhook(self, payload: SePayWebhookPayload) -> None:
        provider = PaymentProvider.SEPAY
        existing = self.repository.get_transaction(provider, payload.transaction_id)
        if existing is not None:
            return

        now = datetime.now(timezone.utc)
        payment_code = self._resolve_payment_code(payload)
        try:
            order = self._lock_order_context(payment_code)
            disposition = self._non_application_disposition(payload, order, now)

            if disposition is None and order is not None:
                try:
                    SubscriptionService(self.db).apply_payment_no_commit(
                        recruiter_id=order.recruiter_id,
                        plan_id=order.plan_id,
                        duration_days=order.duration_days_snapshot,
                        now=now,
                    )
                except PaymentPlanConflictError:
                    disposition = PaymentDisposition.UNMATCHED
                else:
                    order.status = PaymentOrderStatus.PAID
                    order.paid_at = now
                    order.updated_at = now
                    disposition = PaymentDisposition.APPLIED

            transaction = PaymentTransaction(
                payment_order_id=order.id if order is not None else None,
                provider=provider,
                provider_transaction_id=payload.transaction_id,
                amount=payload.amount,
                transaction_date=payload.transaction_date,
                reference_code=self._trim(payload.reference_code, 255),
                content=self._trim(payload.content, 2000),
                destination_account=self._trim(payload.destination_account, 128),
                disposition=disposition or PaymentDisposition.UNMATCHED,
                created_at=now,
            )
            self.repository.add(transaction)
            self.repository.flush()
            self.repository.commit()
        except IntegrityError:
            self.repository.rollback()
            if self.repository.get_transaction(provider, payload.transaction_id) is not None:
                return
            raise
        except Exception:
            self.repository.rollback()
            raise

    def _lock_order_context(self, payment_code: str | None) -> PaymentOrder | None:
        if payment_code is None:
            return None
        candidate = self.repository.get_order_by_code(payment_code)
        if candidate is None:
            return None

        # Keep the same lock order used by order creation/admin subscription changes:
        # recruiter -> plan -> active subscriptions -> payment order.
        self.repository.get_recruiter_for_update(candidate.recruiter_id)
        self.repository.get_plan_for_update(candidate.plan_id)
        self.repository.active_subscriptions_for_update(candidate.recruiter_id)
        return self.repository.get_order_by_code_for_update(payment_code)

    def _non_application_disposition(
        self,
        payload: SePayWebhookPayload,
        order: PaymentOrder | None,
        now: datetime,
    ) -> PaymentDisposition | None:
        if payload.transfer_type != "in":
            return PaymentDisposition.OUTGOING_IGNORED
        if self._normalize_account(payload.destination_account) != self._normalize_account(
            self._bank_configuration().account_number
        ):
            return PaymentDisposition.ACCOUNT_MISMATCH
        if order is None:
            return PaymentDisposition.UNMATCHED
        if order.status == PaymentOrderStatus.PAID:
            return PaymentDisposition.UNMATCHED
        if order.status == PaymentOrderStatus.CANCELLED:
            return PaymentDisposition.ORDER_CANCELLED
        if order.status == PaymentOrderStatus.EXPIRED or order.expires_at <= now:
            if order.status == PaymentOrderStatus.PENDING:
                order.status = PaymentOrderStatus.EXPIRED
                order.updated_at = now
            return PaymentDisposition.ORDER_EXPIRED
        if order.status != PaymentOrderStatus.PENDING:
            return PaymentDisposition.UNMATCHED
        if payload.amount != order.amount:
            return PaymentDisposition.AMOUNT_MISMATCH
        return None

    def _resolve_payment_code(self, payload: SePayWebhookPayload) -> str | None:
        explicit = (payload.payment_code or "").strip().upper()
        if explicit:
            return explicit
        content = (payload.content or "").upper()
        prefix = re.escape(settings.SEPAY_PAYMENT_CODE_PREFIX)
        match = re.search(rf"(?<![A-Z0-9])({prefix}[A-Z0-9]{{12}})(?![A-Z0-9])", content)
        return match.group(1) if match else None

    def _new_payment_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(8):
            candidate = settings.SEPAY_PAYMENT_CODE_PREFIX + "".join(
                secrets.choice(alphabet) for _ in range(12)
            )
            if not self.repository.payment_code_exists(candidate):
                return candidate
        raise RuntimeError("Unable to allocate a unique payment code.")

    def _response(
        self, order: PaymentOrder, bank: PaymentBankConfiguration
    ) -> PaymentOrderResponse:
        amount = format(order.amount, "f")
        query = urlencode(
            {
                "amount": amount,
                "addInfo": order.payment_code,
                "accountName": bank.account_name,
            }
        )
        qr_url = (
            f"https://img.vietqr.io/image/{quote(bank.bank_bin, safe='')}-"
            f"{quote(bank.account_number, safe='')}-compact2.png?{query}"
        )
        return PaymentOrderResponse(
            id=order.id,
            status=order.status,
            plan=PaymentPlanSnapshotResponse(
                id=order.plan_id,
                code=order.plan_code_snapshot,
                name=order.plan_name_snapshot,
                billing_period=order.billing_period_snapshot,
                duration_days=order.duration_days_snapshot,
            ),
            amount=order.amount,
            currency=order.currency,
            payment_code=order.payment_code,
            transfer_content=order.payment_code,
            bank=PaymentBankResponse(
                bank_name=bank.bank_name,
                bank_bin=bank.bank_bin,
                account_number=bank.account_number,
                account_name=bank.account_name,
            ),
            qr=PaymentQrResponse(image_url=qr_url),
            expires_at=order.expires_at,
            paid_at=order.paid_at,
            created_at=order.created_at,
        )

    @staticmethod
    def _bank_configuration() -> PaymentBankConfiguration:
        values = {
            "bank_name": settings.SEPAY_BANK_NAME,
            "bank_bin": settings.SEPAY_BANK_BIN,
            "account_number": settings.SEPAY_BANK_ACCOUNT,
            "account_name": settings.SEPAY_ACCOUNT_NAME,
        }
        missing = [name for name, value in values.items() if not value or not value.strip()]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment receiving account is not configured.",
            )
        return PaymentBankConfiguration(
            **{name: str(value).strip() for name, value in values.items()}
        )

    @staticmethod
    def _normalize_account(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    @staticmethod
    def _trim(value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized[:limit] if normalized else None
