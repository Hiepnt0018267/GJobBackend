"""Candidate-facing, cache-only job recommendation contract."""

import uuid
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse


class JobRecommendationStatus(str, Enum):
    ranked = "ranked"
    pending = "pending"
    unavailable = "unavailable"
    error = "error"


class JobRecommendationReasonCode(str, Enum):
    shared_skill = "shared_skill"


class JobRecommendationReason(BaseModel):
    """Contextual evidence only; never a causal explanation or probability."""

    code: JobRecommendationReasonCode
    message: str
    evidence: list[str] = Field(default_factory=list, max_length=1)


class CandidateJobRecommendationItem(JobResponse):
    recommendation_rank: int | None = None
    recommendation_status: JobRecommendationStatus
    reasons: list[JobRecommendationReason] = Field(default_factory=list, max_length=3)


class CandidateJobRecommendationListResponse(BaseModel):
    items: list[CandidateJobRecommendationItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    ranking_snapshot: str
    selected_cv_id: uuid.UUID | None
    candidate_signal_status: JobRecommendationStatus
    ranked_count: int
    pending_count: int
    unavailable_count: int
    error_count: int
