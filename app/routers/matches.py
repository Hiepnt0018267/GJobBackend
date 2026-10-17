"""Authorization-scoped on-demand CV/job matching APIs."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.matching import CandidateMatchRequest, CVJobMatchResponse
from app.schemas.subscription import RecruiterFeature
from app.services.cv_job_match_service import CVJobMatchService
from app.services.recruiter_entitlement_service import RecruiterEntitlementService


router = APIRouter(tags=["Matching"])


@router.post(
    "/candidate/jobs/{job_id}/match",
    response_model=CVJobMatchResponse,
    summary="Match one candidate-owned CV against an approved job",
)
async def match_candidate_cv_to_job(
    job_id: uuid.UUID,
    payload: CandidateMatchRequest,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
) -> CVJobMatchResponse:
    return await CVJobMatchService(db).match_for_candidate(
        current_user,
        payload.cv_id,
        job_id,
    )


@router.post(
    "/recruiters/applications/{application_id}/match",
    response_model=CVJobMatchResponse,
    summary="Match the submitted CV for a recruiter-owned application",
)
async def match_recruiter_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
) -> CVJobMatchResponse:
    RecruiterEntitlementService(db).require_feature(
        current_user, RecruiterFeature.DETAILED_CV_JD_MATCH
    )
    return await CVJobMatchService(db).match_for_recruiter_application(
        current_user,
        application_id,
    )
