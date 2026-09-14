import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.cv_extraction import CVExtraction, CVExtractionStatus

if TYPE_CHECKING:
    from app.models.cv import CV


class CVExtractionStateError(RuntimeError):
    """Raised when a terminal update loses its expected PROCESSING state."""


class CVExtractionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_for_cv(self, cv_id: uuid.UUID) -> CVExtraction | None:
        return (
            self.db.query(CVExtraction)
            .filter(
                CVExtraction.cv_id == cv_id,
                CVExtraction.status == CVExtractionStatus.PROCESSING,
            )
            .first()
        )

    def get_latest_for_cv(self, cv_id: uuid.UUID) -> CVExtraction | None:
        return (
            self.db.query(CVExtraction)
            .filter(CVExtraction.cv_id == cv_id)
            .order_by(CVExtraction.created_at.desc(), CVExtraction.id.desc())
            .first()
        )

    def has_confirmed_for_cv(self, cv_id: uuid.UUID) -> bool:
        """Check authoritative uploaded-CV readiness without loading extraction history."""
        return (
            self.db.query(CVExtraction.id)
            .filter(
                CVExtraction.cv_id == cv_id,
                CVExtraction.status == CVExtractionStatus.SUCCEEDED,
                CVExtraction.confirmed_at.is_not(None),
            )
            .first()
            is not None
        )

    def get_for_cv_for_update(
        self, extraction_id: uuid.UUID, cv_id: uuid.UUID
    ) -> CVExtraction | None:
        return (
            self.db.query(CVExtraction)
            .filter(
                CVExtraction.id == extraction_id,
                CVExtraction.cv_id == cv_id,
            )
            .with_for_update()
            .first()
        )

    def create_processing(self, extraction: CVExtraction) -> None:
        self.db.add(extraction)
        self.db.commit()

    def mark_succeeded(
        self,
        extraction_id: uuid.UUID,
        structured_result: dict[str, object],
        completed_at: datetime,
    ) -> CVExtraction:
        self._terminal_update(
            extraction_id,
            status=CVExtractionStatus.SUCCEEDED,
            structured_result=structured_result,
            error_code=None,
            failure_reason=None,
            completed_at=completed_at,
        )
        return self._require(extraction_id)

    def mark_failed(
        self,
        extraction_id: uuid.UUID,
        error_code: str,
        failure_reason: str,
        completed_at: datetime,
    ) -> CVExtraction:
        self._terminal_update(
            extraction_id,
            status=CVExtractionStatus.FAILED,
            structured_result=None,
            error_code=error_code,
            failure_reason=failure_reason,
            completed_at=completed_at,
        )
        return self._require(extraction_id)

    def _terminal_update(self, extraction_id: uuid.UUID, **values: object) -> None:
        result = self.db.execute(
            update(CVExtraction)
            .where(
                CVExtraction.id == extraction_id,
                CVExtraction.status == CVExtractionStatus.PROCESSING,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise CVExtractionStateError(
                "Extraction is no longer in the expected processing state."
            )
        self.db.commit()

    def _require(self, extraction_id: uuid.UUID) -> CVExtraction:
        extraction = self.db.get(CVExtraction, extraction_id)
        if extraction is None:
            raise CVExtractionStateError("Extraction disappeared after persistence.")
        return extraction

    def rollback(self) -> None:
        self.db.rollback()

    def apply_confirmation(
        self,
        cv: "CV",
        extraction: CVExtraction,
        reviewed_fields: dict[str, object],
        confirmed_at: datetime,
    ) -> tuple["CV", CVExtraction]:
        for field, value in reviewed_fields.items():
            setattr(cv, field, value)
        extraction.confirmed_at = confirmed_at
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(cv)
        self.db.refresh(extraction)
        return cv, extraction
