import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.application import JobApplicationStatus
from app.models.user import User
from app.repositories.candidate_application_repository import CandidateApplicationRepository
from app.schemas.application import (
    CandidateApplicationAppliedSummary,
    CandidateApplicationByJobResponse,
    CandidateApplicationDetail,
    CandidateApplicationListItem,
    CandidateApplicationListResponse,
)


class CandidateApplicationService:
    _WITHDRAWABLE_STATUSES = {
        JobApplicationStatus.SUBMITTED,
        JobApplicationStatus.REVIEWING,
        JobApplicationStatus.SHORTLISTED,
    }

    def __init__(self, db: Session) -> None:
        self.repository = CandidateApplicationRepository(db)

    def list_applications(
        self,
        current_user: User,
        application_status: JobApplicationStatus | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> CandidateApplicationListResponse:
        normalized_search = " ".join(search.split()) if search else None
        items, total = self.repository.list_for_candidate(
            current_user.id,
            application_status,
            normalized_search,
            page,
            page_size,
        )
        return CandidateApplicationListResponse(
            items=[CandidateApplicationListItem.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_application(
        self, current_user: User, application_id: uuid.UUID
    ) -> CandidateApplicationDetail:
        application = self.repository.get_owned(application_id, current_user.id)
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        return CandidateApplicationDetail.model_validate(application)

    def withdraw_application(
        self, current_user: User, application_id: uuid.UUID
    ) -> CandidateApplicationDetail:
        application = self.repository.get_owned(application_id, current_user.id)
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        if application.status not in self._WITHDRAWABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application cannot be withdrawn in its current status.",
            )

        try:
            withdrawn = self.repository.withdraw_if_eligible(
                application_id, current_user.id, application.status, current_user.id
            )
        except Exception:
            self.repository.rollback()
            raise

        if not withdrawn:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application status changed. Please try again.",
            )

        updated_application = self.repository.get_owned(application_id, current_user.id)
        if updated_application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        return CandidateApplicationDetail.model_validate(updated_application)

    def get_application_status_for_job(
        self, current_user: User, job_id: uuid.UUID
    ) -> CandidateApplicationByJobResponse:
        application = self.repository.get_by_candidate_and_job(current_user.id, job_id)
        if application is None:
            return CandidateApplicationByJobResponse(has_applied=False)
        return CandidateApplicationByJobResponse(
            has_applied=True,
            application=CandidateApplicationAppliedSummary.model_validate(application),
        )
