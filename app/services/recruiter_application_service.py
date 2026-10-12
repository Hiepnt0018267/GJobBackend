import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.application import JobApplicationStatus
from app.models.cv import CVSourceType
from app.models.notification import NotificationType
from app.models.user import User
from app.repositories.recruiter_application_repository import RecruiterApplicationRepository
from app.schemas.recruiter_application import (
    RecruiterApplicationDetail,
    RecruiterApplicationListItem,
    RecruiterApplicationListResponse,
    RecruiterApplicationSort,
    ApplicantRankingMode,
)
from app.services.cv_storage_service import CVStorageService
from app.services.notification_event_service import NotificationEventService


class RecruiterApplicationService:
    """Recruiter applicant workflow for applications on recruiter-owned jobs only."""

    _ACTIONS: dict[str, tuple[JobApplicationStatus, JobApplicationStatus, str]] = {
        "review": (JobApplicationStatus.SUBMITTED, JobApplicationStatus.REVIEWING, "reviewed"),
        "shortlist": (JobApplicationStatus.REVIEWING, JobApplicationStatus.SHORTLISTED, "shortlisted"),
        "hire": (JobApplicationStatus.SHORTLISTED, JobApplicationStatus.HIRED, "hired"),
    }
    _REJECTABLE_STATUSES = {
        JobApplicationStatus.SUBMITTED,
        JobApplicationStatus.REVIEWING,
        JobApplicationStatus.SHORTLISTED,
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RecruiterApplicationRepository(db)
        self.storage = CVStorageService()
        self.notification_events = NotificationEventService(db)

    @staticmethod
    def _application_or_404(application_id: uuid.UUID, recruiter_id: uuid.UUID, repository: RecruiterApplicationRepository):
        application = repository.get_owned_application(application_id, recruiter_id)
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        return application

    @staticmethod
    def _job_or_404(job_id: uuid.UUID, recruiter_id: uuid.UUID, repository: RecruiterApplicationRepository) -> None:
        if repository.get_owned_job(job_id, recruiter_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    def list_applications(
        self,
        current_user: User,
        application_status: JobApplicationStatus | None,
        search: str | None,
        job_id: uuid.UUID | None,
        page: int,
        page_size: int,
        sort: RecruiterApplicationSort = RecruiterApplicationSort.newest,
        ai_top_n: int | None = None,
        ranking_snapshot: str | None = None,
        ranking_mode: ApplicantRankingMode | None = None,
        top_n: int | None = None,
    ) -> RecruiterApplicationListResponse:
        from app.services.applicant_ranking_service import validate_ranking_options
        if top_n is not None and ranking_mode is None:
            raise HTTPException(422, "top_n requires ranking_mode=top_n.")
        if ranking_mode is not None and ai_top_n is not None:
            raise HTTPException(422, "Do not combine legacy ai_top_n with ranking_mode.")
        validate_ranking_options(ranking_mode, top_n)
        normalized_search = " ".join(search.split()) if search else None
        if sort == RecruiterApplicationSort.ai_match:
            if job_id is not None:
                self._job_or_404(job_id, current_user.id, self.repository)
            # Full owner-filtered query FIRST; no AI before authorization.
            items, _ = self.repository.list_owned_applications(
                current_user.id, application_status, normalized_search, job_id, None, None
            )
            from app.services.applicant_ranking_service import ApplicantRankingService
            return ApplicantRankingService(self.db).list(items, owner=current_user.id,
                filters=[str(job_id) if job_id else None,
                         application_status.value if application_status else None, normalized_search],
                page=page, page_size=page_size, top_n=top_n if ranking_mode else ai_top_n,
                snapshot=ranking_snapshot, ranking_mode=ranking_mode)
        if ai_top_n is not None or ranking_snapshot is not None or ranking_mode is not None:
            raise HTTPException(422, "AI result options require sort=ai_match.")
        items, total = self.repository.list_owned_applications(
            current_user.id,
            application_status,
            normalized_search,
            job_id,
            page,
            page_size,
        )
        return RecruiterApplicationListResponse(
            items=[RecruiterApplicationListItem.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def list_job_applications(
        self,
        current_user: User,
        job_id: uuid.UUID,
        application_status: JobApplicationStatus | None,
        search: str | None,
        page: int,
        page_size: int,
        sort: RecruiterApplicationSort = RecruiterApplicationSort.newest,
        ai_top_n: int | None = None,
        ranking_snapshot: str | None = None,
        ranking_mode: ApplicantRankingMode | None = None,
        top_n: int | None = None,
    ) -> RecruiterApplicationListResponse:
        self._job_or_404(job_id, current_user.id, self.repository)
        return self.list_applications(
            current_user,
            application_status,
            search,
            job_id,
            page,
            page_size,
            sort,
            ai_top_n,
            ranking_snapshot,
            ranking_mode,
            top_n,
        )

    def get_application(
        self, current_user: User, application_id: uuid.UUID
    ) -> RecruiterApplicationDetail:
        return RecruiterApplicationDetail.model_validate(
            self._application_or_404(application_id, current_user.id, self.repository)
        )

    def get_uploaded_cv_file(self, current_user: User, application_id: uuid.UUID):
        application = self._application_or_404(application_id, current_user.id, self.repository)
        if application.cv.source_type != CVSourceType.UPLOADED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This application does not use an uploaded CV file.")
        try:
            return application.cv, self.storage.get_file_path(application.cv.storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded CV file not found.") from exc

    def get_cv_photo(self, current_user: User, application_id: uuid.UUID):
        application = self._application_or_404(application_id, current_user.id, self.repository)
        if application.cv.source_type != CVSourceType.BUILDER or not application.cv.photo_storage_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV photo not found.")
        try:
            return self.storage.get_file_path(application.cv.photo_storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV photo not found.") from exc

    def transition_application(
        self, current_user: User, application_id: uuid.UUID, action: str
    ) -> RecruiterApplicationDetail:
        application = self._application_or_404(application_id, current_user.id, self.repository)
        if action == "reject":
            if application.status not in self._REJECTABLE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Application cannot be rejected in its current status.",
                )
            next_status = JobApplicationStatus.REJECTED
        else:
            expected_status, next_status, action_label = self._ACTIONS[action]
            if application.status != expected_status:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Application cannot be {action_label} in its current status.",
                )

        try:
            transitioned = self.repository.transition_if_current(
                application_id,
                current_user.id,
                application.status,
                next_status,
                current_user.id,
            )
        except Exception:
            self.repository.rollback()
            raise

        if not transitioned:
            self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application status changed. Please try again.",
            )
        try:
            self.notification_events.create_application_notification(
                application.candidate_id,
                NotificationType.APPLICATION_STATUS_CHANGED,
                application.id,
                application.job.title,
                status=next_status,
            )
            self.db.commit()
            self.db.expire_all()
        except Exception:
            self.repository.rollback()
            raise
        return RecruiterApplicationDetail.model_validate(
            self._application_or_404(application_id, current_user.id, self.repository)
        )
