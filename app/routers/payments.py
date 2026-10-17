import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.payment import PaymentDisposition, PaymentOrderStatus
from app.models.user import User, UserRole
from app.schemas.payment import (
    AdminPaymentOrderDetailResponse,
    AdminPaymentOrderListResponse,
    AdminPaymentSummaryResponse,
    AdminPaymentTransactionListResponse,
    AdminPaymentTransactionRecordResponse,
    PaymentOrderCreateRequest,
    PaymentOrderResponse,
    SePayWebhookPayload,
    SePayWebhookResponse,
)
from app.services.admin_payment_service import AdminPaymentService
from app.services.payment_service import PaymentService
from app.services.sepay_webhook import SePayWebhookVerifier


router = APIRouter(tags=["Payments"])
MAX_WEBHOOK_BODY_BYTES = 64 * 1024


@router.get("/admin/payments/summary", response_model=AdminPaymentSummaryResponse)
def get_admin_payment_summary(
    plan_code: str | None = Query(default=None, max_length=64),
    recruiter_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminPaymentService(db).summary(
        plan_code=plan_code, recruiter_id=recruiter_id, date_from=date_from, date_to=date_to
    )


@router.get(
    "/admin/payment-transactions",
    response_model=AdminPaymentTransactionListResponse,
)
def list_admin_payment_transactions(
    search: str | None = Query(default=None, max_length=100),
    disposition: PaymentDisposition | None = Query(default=None),
    order_status: PaymentOrderStatus | None = Query(default=None),
    plan_code: str | None = Query(default=None, max_length=64),
    recruiter_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminPaymentService(db).list_transactions(
        search=search,
        disposition=disposition,
        order_status=order_status,
        plan_code=plan_code,
        recruiter_id=recruiter_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/admin/payment-transactions/{transaction_id}",
    response_model=AdminPaymentTransactionRecordResponse,
)
def get_admin_payment_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminPaymentService(db).get_transaction(transaction_id)


@router.get("/admin/payment-orders", response_model=AdminPaymentOrderListResponse)
def list_admin_payment_orders(
    search: str | None = Query(default=None, max_length=100),
    order_status: PaymentOrderStatus | None = Query(default=None),
    plan_code: str | None = Query(default=None, max_length=64),
    recruiter_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminPaymentService(db).list_orders(
        search=search,
        order_status=order_status,
        plan_code=plan_code,
        recruiter_id=recruiter_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/admin/payment-orders/{order_id}", response_model=AdminPaymentOrderDetailResponse
)
def get_admin_payment_order(
    order_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminPaymentService(db).get_order(order_id)


@router.post(
    "/recruiter/payment-orders",
    response_model=PaymentOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_order(
    payload: PaymentOrderCreateRequest,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return PaymentService(db).create_order(current_user, payload.plan_id)


@router.get(
    "/recruiter/payment-orders/{order_id}",
    response_model=PaymentOrderResponse,
)
def get_payment_order(
    order_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return PaymentService(db).get_order(current_user, order_id)


@router.post(
    "/recruiter/payment-orders/{order_id}/cancel",
    response_model=PaymentOrderResponse,
)
def cancel_payment_order(
    order_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return PaymentService(db).cancel_order(current_user, order_id)


@router.post(
    "/payments/sepay/webhook",
    response_model=SePayWebhookResponse,
)
async def receive_sepay_webhook(
    request: Request,
    signature: str | None = Header(default=None, alias="X-SePay-Signature"),
    timestamp: str | None = Header(default=None, alias="X-SePay-Timestamp"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Webhook payload is too large.",
        )
    SePayWebhookVerifier(settings.SEPAY_WEBHOOK_SECRET).verify(
        raw_body=raw_body,
        signature=signature,
        timestamp=timestamp,
    )
    try:
        payload = SePayWebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed SePay webhook payload.",
        ) from exc
    PaymentService(db).process_sepay_webhook(payload)
    return SePayWebhookResponse()
