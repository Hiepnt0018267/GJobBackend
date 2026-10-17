import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.payment import PaymentDisposition, PaymentOrderStatus, PaymentProvider


class PaymentOrderCreateRequest(BaseModel):
    plan_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class PaymentPlanSnapshotResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    billing_period: str
    duration_days: int


class PaymentBankResponse(BaseModel):
    bank_name: str
    bank_bin: str
    account_number: str
    account_name: str


class PaymentQrResponse(BaseModel):
    image_url: str


class PaymentOrderResponse(BaseModel):
    id: uuid.UUID
    status: PaymentOrderStatus
    plan: PaymentPlanSnapshotResponse
    amount: Decimal
    currency: str
    payment_code: str
    transfer_content: str
    bank: PaymentBankResponse
    qr: PaymentQrResponse
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime


class SePayWebhookPayload(BaseModel):
    transaction_id: str = Field(alias="id")
    payment_code: str | None = Field(default=None, alias="code")
    content: str | None = None
    amount: Decimal = Field(alias="transferAmount", ge=0)
    transfer_type: str = Field(alias="transferType")
    transaction_date: datetime = Field(alias="transactionDate")
    reference_code: str | None = Field(default=None, alias="referenceCode")
    destination_account: str = Field(alias="accountNumber")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("transaction_id", mode="before")
    @classmethod
    def stringify_transaction_id(cls, value: object) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("SePay transaction id is required.")
        return normalized

    @field_validator("transaction_date", mode="before")
    @classmethod
    def parse_transaction_date(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized and "T" not in normalized:
                return normalized.replace(" ", "T", 1) + "+07:00"
        return value

    @field_validator("transfer_type")
    @classmethod
    def normalize_transfer_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("SePay transfer type is required.")
        return normalized


class SePayWebhookResponse(BaseModel):
    success: bool = True


class AdminPaymentRecruiterResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class AdminPaymentOrderSummaryResponse(BaseModel):
    id: uuid.UUID
    payment_code: str
    status: PaymentOrderStatus
    plan_code: str
    plan_name: str
    amount: Decimal
    currency: str
    expires_at: datetime
    paid_at: datetime | None
    created_at: datetime
    recruiter: AdminPaymentRecruiterResponse


class AdminPaymentTransactionRecordResponse(BaseModel):
    id: uuid.UUID
    provider: PaymentProvider
    provider_transaction_id: str
    amount: Decimal
    transaction_date: datetime
    reference_code: str | None
    content: str | None
    destination_account: str | None
    disposition: PaymentDisposition
    created_at: datetime
    order: AdminPaymentOrderSummaryResponse | None


class AdminPaymentTransactionListResponse(BaseModel):
    items: list[AdminPaymentTransactionRecordResponse]
    total: int
    page: int
    page_size: int


class AdminPaymentOrderListResponse(BaseModel):
    items: list[AdminPaymentOrderSummaryResponse]
    total: int
    page: int
    page_size: int


class AdminPaymentOrderDetailResponse(AdminPaymentOrderSummaryResponse):
    billing_period: str
    duration_days: int
    transactions: list[AdminPaymentTransactionRecordResponse]


class AdminPaymentSummaryResponse(BaseModel):
    successful_transactions: int
    revenue: Decimal
    needs_review: int
    pending_orders: int
    paid_orders: int
