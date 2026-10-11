import uuid
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import JobApplicationStatus
from app.models.cv import CVSourceType
from app.models.job import JobStatus
from app.schemas.cv import CVResponse
from app.schemas.cv_template import CVTemplateSummary
from app.schemas.job import JobResponse


class RecruiterApplicationCandidateSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationCandidateDetail(RecruiterApplicationCandidateSummary):
    phone: str | None


class RecruiterApplicationJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    status: JobStatus

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationCVSummary(BaseModel):
    id: uuid.UUID
    title: str
    source_type: CVSourceType
    template: CVTemplateSummary | None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationSort(str, Enum):
    newest = "newest"
    ai_match = "ai_match"


class ApplicantRankingStatus(str, Enum):
    ranked = "ranked"
    pending = "pending"
    unavailable = "unavailable"
    error = "error"


class ApplicantRankingMode(str, Enum):
    all = "all"
    top_n = "top_n"


class RecruiterApplicationListItem(BaseModel):
    ai_rank: int | None = None
    ranking_status: ApplicantRankingStatus | None = None
    semantic_match_score: float | None = None
    id: uuid.UUID
    status: JobApplicationStatus
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    cv_id: uuid.UUID
    candidate: RecruiterApplicationCandidateSummary
    job: RecruiterApplicationJobSummary
    cv: RecruiterApplicationCVSummary
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationDetail(RecruiterApplicationListItem):
    candidate: RecruiterApplicationCandidateDetail
    job: JobResponse
    cv: CVResponse


class RecruiterApplicationListResponse(BaseModel):
    ranking_mode: ApplicantRankingMode | None = None
    requested_top_n: int | None = None
    ranked_available_count: int | None = None
    returned_ranked_count: int | None = None
    unranked_count: int | None = None
    ranking_snapshot: str | None = None
    items: list[RecruiterApplicationListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
