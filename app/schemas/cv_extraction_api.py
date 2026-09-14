import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.cv_extraction import CVExtractionStatus
from app.schemas.cv import CVResponse
from app.schemas.cv_extraction import StructuredCVExtractionResult


class CVExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cv_id: uuid.UUID
    status: CVExtractionStatus
    provider: str
    model: str
    result: StructuredCVExtractionResult | None = Field(
        default=None, validation_alias="structured_result"
    )
    error_code: str | None
    failure_reason: str | None
    started_at: datetime
    completed_at: datetime | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_status_payload(self):
        if (
            self.confirmed_at is not None
            and self.status != CVExtractionStatus.SUCCEEDED
        ):
            raise ValueError("only a succeeded extraction can be confirmed")
        if self.status == CVExtractionStatus.PROCESSING:
            valid = (
                self.result is None
                and self.error_code is None
                and self.failure_reason is None
                and self.completed_at is None
            )
        elif self.status == CVExtractionStatus.SUCCEEDED:
            valid = (
                self.result is not None
                and self.error_code is None
                and self.failure_reason is None
                and self.completed_at is not None
            )
        else:
            valid = (
                self.result is None
                and self.error_code is not None
                and self.failure_reason is not None
                and self.completed_at is not None
            )
        if not valid:
            raise ValueError("extraction status and payload are inconsistent")
        return self


class CVExtractionConfirmationResponse(BaseModel):
    cv_id: uuid.UUID
    extraction_id: uuid.UUID
    confirmed_at: datetime
    cv: CVResponse
