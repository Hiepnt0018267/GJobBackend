from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job import JobStatus
from app.models.recruiter_profile import RecruiterProfile
from app.models.user import User
from app.repositories.recruiter_repository import RecruiterRepository
from app.repositories.user_repository import UserRepository
from app.schemas.recruiter import RecruiterDashboardSummary, RecruiterProfileResponse, UpdateRecruiterProfileRequest


class RecruiterService:
    def __init__(self, db: Session) -> None:
        self.recruiter_repo = RecruiterRepository(db)
        self.user_repo = UserRepository(db)

    def _get_or_create_profile(self, user: User) -> RecruiterProfile:
        profile = self.recruiter_repo.get_by_user_id(user.id)
        return profile if profile is not None else self.recruiter_repo.create(RecruiterProfile(user_id=user.id))

    @staticmethod
    def _response(user: User, profile: RecruiterProfile) -> RecruiterProfileResponse:
        return RecruiterProfileResponse(
            id=user.id, email=user.email, full_name=user.full_name, phone=user.phone,
            company_name=profile.company_name, company_website=profile.company_website,
            company_description=profile.company_description, company_address=profile.company_address,
            company_logo_url=profile.company_logo_url, industry=profile.industry,
            company_size=profile.company_size, created_at=profile.created_at, updated_at=profile.updated_at,
        )

    def get_profile(self, user: User) -> RecruiterProfileResponse:
        return self._response(user, self._get_or_create_profile(user))

    def update_profile(self, user: User, payload: UpdateRecruiterProfileRequest) -> RecruiterProfileResponse:
        profile = self._get_or_create_profile(user)
        values = payload.model_dump(exclude_unset=True)
        user_fields = {key: values.pop(key) for key in ("full_name", "phone") if key in values}
        if user_fields:
            user_fields["updated_at"] = datetime.now(timezone.utc)
            user = self.user_repo.update(user, user_fields)
        if values:
            values["updated_at"] = datetime.now(timezone.utc)
            profile = self.recruiter_repo.update(profile, values)
        return self._response(user, profile)

    def dashboard_summary(self, user: User) -> RecruiterDashboardSummary:
        counts = self.recruiter_repo.job_counts(user.id)
        return RecruiterDashboardSummary(
            total_jobs=sum(counts.values()), pending_jobs=counts.get(JobStatus.PENDING, 0),
            approved_jobs=counts.get(JobStatus.APPROVED, 0), rejected_jobs=counts.get(JobStatus.REJECTED, 0),
            closed_jobs=counts.get(JobStatus.CLOSED, 0),
        )
