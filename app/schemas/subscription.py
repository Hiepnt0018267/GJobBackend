import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from enum import Enum
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.subscription import BillingPeriod, SubscriptionSource, SubscriptionStatus


PLAN_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def validate_plan_semantics(
    *, code: str, price: Decimal, currency: str, billing_period: BillingPeriod, duration_days: int | None
) -> None:
    if currency != "VND":
        raise ValueError("currency must be VND")
    if code == "FREE":
        if price != Decimal("0") or billing_period != BillingPeriod.NONE or duration_days is not None:
            raise ValueError("FREE must have price 0, billing_period NONE, and no duration_days")
    elif price <= 0:
        raise ValueError("paid plans must have price greater than 0")
    elif billing_period != BillingPeriod.MONTHLY or duration_days is None:
        raise ValueError("paid plans must have billing_period MONTHLY and positive duration_days")


class SubscriptionPlanCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(max_digits=18, decimal_places=0, ge=0)
    currency: str = Field(default="VND", min_length=3, max_length=3)
    billing_period: BillingPeriod
    duration_days: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().upper()
            if not PLAN_CODE_PATTERN.fullmatch(value):
                raise ValueError("code must contain only uppercase letters, digits, and underscores")
        return value

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def valid_semantics(self):
        validate_plan_semantics(
            code=self.code,
            price=self.price,
            currency=self.currency,
            billing_period=self.billing_period,
            duration_days=self.duration_days,
        )
        return self


class SubscriptionPlanUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price: Decimal | None = Field(default=None, max_digits=18, decimal_places=0, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    billing_period: BillingPeriod | None = None
    duration_days: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class SubscriptionPlanResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    price: Decimal
    currency: str
    billing_period: BillingPeriod
    duration_days: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionPlanListResponse(BaseModel):
    items: list[SubscriptionPlanResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class SubscriptionGrantRequest(BaseModel):
    model_config = {"extra": "forbid"}

    plan_id: uuid.UUID
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("starts_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("datetime must include a timezone offset")
            return value.astimezone(timezone.utc)
        return None

    @model_validator(mode="after")
    def valid_interval(self):
        if self.starts_at is not None and self.expires_at is not None and self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be later than starts_at")
        return self


class EffectivePlanResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    price: Decimal
    currency: str
    billing_period: BillingPeriod

    model_config = {"from_attributes": True}


class CurrentSubscriptionResponse(BaseModel):
    id: uuid.UUID
    status: SubscriptionStatus
    starts_at: datetime
    expires_at: datetime | None
    source: SubscriptionSource

    model_config = {"from_attributes": True}


class EffectiveSubscriptionResponse(BaseModel):
    effective_plan: EffectivePlanResponse
    subscription: CurrentSubscriptionResponse | None


class RecruiterFeature(str, Enum):
    AI_CANDIDATE_RANKING = "AI_CANDIDATE_RANKING"
    DETAILED_CV_JD_MATCH = "DETAILED_CV_JD_MATCH"


class RecruiterEffectiveSubscriptionResponse(EffectiveSubscriptionResponse):
    entitlements: dict[RecruiterFeature, bool]


class RecruiterPlanFeatureResponse(BaseModel):
    key: RecruiterFeature
    label: str
    included: bool


class RecruiterPlanCatalogItem(SubscriptionPlanResponse):
    features: list[RecruiterPlanFeatureResponse]


class RecruiterFeature(str, Enum):
    AI_CANDIDATE_RANKING = "AI_CANDIDATE_RANKING"
    DETAILED_CV_JD_MATCH = "DETAILED_CV_JD_MATCH"


class RecruiterEffectiveSubscriptionResponse(EffectiveSubscriptionResponse):
    entitlements: dict[RecruiterFeature, bool]


class RecruiterPlanFeatureResponse(BaseModel):
    key: RecruiterFeature
    label: str
    included: bool


class RecruiterPlanCatalogItem(SubscriptionPlanResponse):
    features: list[RecruiterPlanFeatureResponse]


class RecruiterFeature(str, Enum):
    AI_CANDIDATE_RANKING = "AI_CANDIDATE_RANKING"
    DETAILED_CV_JD_MATCH = "DETAILED_CV_JD_MATCH"


class RecruiterEffectiveSubscriptionResponse(EffectiveSubscriptionResponse):
    entitlements: dict[RecruiterFeature, bool]


class RecruiterPlanFeatureResponse(BaseModel):
    key: RecruiterFeature
    label: str
    included: bool


class RecruiterPlanCatalogItem(SubscriptionPlanResponse):
    features: list[RecruiterPlanFeatureResponse]


class AdminRecruiterSubscriptionItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    effective_plan: EffectivePlanResponse
    subscription: CurrentSubscriptionResponse | None


class AdminRecruiterSubscriptionListResponse(BaseModel):
    items: list[AdminRecruiterSubscriptionItem]
    page: int
    page_size: int
    total: int
    total_pages: int
