import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.payment import PaymentDisposition, PaymentOrder, PaymentOrderStatus, PaymentTransaction
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import (
    AdminPaymentOrderDetailResponse,
    AdminPaymentOrderListResponse,
    AdminPaymentOrderSummaryResponse,
    AdminPaymentRecruiterResponse,
    AdminPaymentSummaryResponse,
    AdminPaymentTransactionListResponse,
    AdminPaymentTransactionRecordResponse,
)


class AdminPaymentService:
    def __init__(self, db: Session) -> None:
        self.repository = PaymentRepository(db)

    def list_transactions(
        self,
        *,
        search: str | None,
        disposition: PaymentDisposition | None,
        order_status: PaymentOrderStatus | None,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> AdminPaymentTransactionListResponse:
        date_from, date_to = self._validated_dates(date_from, date_to)
        rows, total = self.repository.list_admin_transactions(
            search=self._clean(search),
            disposition=disposition,
            order_status=order_status,
            plan_code=self._clean(plan_code, upper=True),
            recruiter_id=recruiter_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return AdminPaymentTransactionListResponse(
            items=[self._transaction_response(*row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_transaction(self, transaction_id: uuid.UUID) -> AdminPaymentTransactionRecordResponse:
        row = self.repository.get_admin_transaction(transaction_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment transaction not found.")
        return self._transaction_response(*row)

    def list_orders(
        self,
        *,
        search: str | None,
        order_status: PaymentOrderStatus | None,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        page_size: int,
    ) -> AdminPaymentOrderListResponse:
        date_from, date_to = self._validated_dates(date_from, date_to)
        rows, total = self.repository.list_admin_orders(
            search=self._clean(search),
            order_status=order_status,
            plan_code=self._clean(plan_code, upper=True),
            recruiter_id=recruiter_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return AdminPaymentOrderListResponse(
            items=[self._order_response(*row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_order(self, order_id: uuid.UUID) -> AdminPaymentOrderDetailResponse:
        row = self.repository.get_admin_order(order_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found.")
        order, recruiter = row
        order_response = self._order_response(order, recruiter)
        transactions = [
            self._transaction_response(transaction, order, recruiter)
            for transaction in self.repository.list_order_transactions(order.id)
        ]
        return AdminPaymentOrderDetailResponse(
            **order_response.model_dump(),
            billing_period=order.billing_period_snapshot,
            duration_days=order.duration_days_snapshot,
            transactions=transactions,
        )

    def summary(
        self,
        *,
        plan_code: str | None,
        recruiter_id: uuid.UUID | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> AdminPaymentSummaryResponse:
        date_from, date_to = self._validated_dates(date_from, date_to)
        return AdminPaymentSummaryResponse(
            **self.repository.admin_payment_summary(
                plan_code=self._clean(plan_code, upper=True),
                recruiter_id=recruiter_id,
                date_from=date_from,
                date_to=date_to,
            )
        )

    @classmethod
    def _transaction_response(
        cls,
        transaction: PaymentTransaction,
        order: PaymentOrder | None,
        recruiter: User | None,
    ) -> AdminPaymentTransactionRecordResponse:
        return AdminPaymentTransactionRecordResponse(
            id=transaction.id,
            provider=transaction.provider,
            provider_transaction_id=transaction.provider_transaction_id,
            amount=transaction.amount,
            transaction_date=transaction.transaction_date,
            reference_code=transaction.reference_code,
            content=transaction.content,
            destination_account=transaction.destination_account,
            disposition=transaction.disposition,
            created_at=transaction.created_at,
            order=cls._order_response(order, recruiter) if order and recruiter else None,
        )

    @classmethod
    def _order_response(
        cls, order: PaymentOrder, recruiter: User
    ) -> AdminPaymentOrderSummaryResponse:
        return AdminPaymentOrderSummaryResponse(
            id=order.id,
            payment_code=order.payment_code,
            status=cls._effective_status(order),
            plan_code=order.plan_code_snapshot,
            plan_name=order.plan_name_snapshot,
            amount=order.amount,
            currency=order.currency,
            expires_at=order.expires_at,
            paid_at=order.paid_at,
            created_at=order.created_at,
            recruiter=AdminPaymentRecruiterResponse(
                id=recruiter.id,
                full_name=recruiter.full_name,
                email=recruiter.email,
            ),
        )

    @staticmethod
    def _effective_status(order: PaymentOrder) -> PaymentOrderStatus:
        expires_at = order.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if order.status == PaymentOrderStatus.PENDING and expires_at <= datetime.now(timezone.utc):
            return PaymentOrderStatus.EXPIRED
        return PaymentOrderStatus(order.status)

    @staticmethod
    def _validated_dates(
        date_from: datetime | None, date_to: datetime | None
    ) -> tuple[datetime | None, datetime | None]:
        for value in (date_from, date_to):
            if value is not None and value.tzinfo is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Payment history dates must include a timezone.",
                )
        if date_from and date_to and date_from >= date_to:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="date_from must be earlier than date_to.",
            )
        return date_from, date_to

    @staticmethod
    def _clean(value: str | None, *, upper: bool = False) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value.upper() if upper else value
