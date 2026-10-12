"""Candidate job recommendations over frozen canonical inputs and vector cache."""

import logging
import math
import time
import uuid

from fastapi import HTTPException

from app.models.skill import normalize_skill_name
from app.repositories.cv_repository import CVRepository
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobResponse
from app.schemas.job_recommendation import (
    CandidateJobRecommendationItem,
    CandidateJobRecommendationListResponse,
    JobRecommendationReason,
    JobRecommendationReasonCode,
    JobRecommendationStatus,
)
from app.services.matching_input_mapper import build_job_matching_input
from app.services.matching_input_service import CVNotReadyForMatchingError, MatchingInputService
from app.services.ranking_cache import RankingCache, digest, entity_identity, runtime_identity
from app.services.semantic_matching_service import cosine_similarity


logger = logging.getLogger(__name__)

RECOMMENDATION_POLICY_VERSION = "candidate-job-recommendation-v1"


def normalize_recommendation_filters(filters: dict) -> dict:
    """Canonical snapshot identity for semantically equivalent request filters."""
    normalized = {}
    for key, value in sorted(filters.items()):
        if hasattr(value, "value"):
            normalized[key] = value.value
        elif isinstance(value, str):
            compact = " ".join(value.split())
            normalized[key] = normalize_skill_name(compact) if key == "skill" else compact.casefold()
        else:
            normalized[key] = value
    return normalized


class CandidateJobRecommendationService:
    def __init__(self, db, cache=None):
        self.cv_repository = CVRepository(db)
        self.job_repository = JobRepository(db)
        self.inputs = MatchingInputService(db)
        self.cache = cache or RankingCache()

    def list(
        self,
        *,
        candidate_id: uuid.UUID,
        cv_id: uuid.UUID | None,
        filters: dict,
        page: int,
        page_size: int,
        snapshot: str | None,
    ) -> CandidateJobRecommendationListResponse:
        started = time.perf_counter()
        cvs, selected_cv, cv_input, selection_state, cv_inputs = self._select_cv(candidate_id, cv_id)
        jobs = self.job_repository.get_recommendation_jobs(candidate_id, **filters)
        job_inputs = {}
        for job in jobs:
            try:
                job_inputs[job.id] = build_job_matching_input(
                    job, [link.skill for link in job.skill_links]
                )
            except (ValueError, TypeError) as exc:
                job_inputs[job.id] = exc

        binding = self._binding(
            candidate_id, cv_id, cvs, selected_cv, cv_input, cv_inputs,
            filters, page_size, jobs, job_inputs,
        )
        snapshot_reused = snapshot is not None
        if snapshot:
            payload = self.cache.load_snapshot(snapshot, binding)
            if not self._valid_snapshot_payload(
                payload, jobs, job_inputs, cv_input, selected_cv
            ):
                raise HTTPException(
                    409,
                    "Recommendation snapshot expired or inputs changed. Restart at page 1.",
                )
        else:
            if page != 1:
                raise HTTPException(422, "Recommendation pages after page 1 require ranking_snapshot.")
            payload = self._rank(jobs, job_inputs, cv_input, selected_cv, selection_state)
            try:
                snapshot = self.cache.save_snapshot(binding, payload)
            except OSError as exc:
                raise HTTPException(
                    503,
                    "Stable recommendation pagination is temporarily unavailable. Use the regular job list.",
                ) from exc

        rows = payload["rows"]
        jobs_by_id = {str(job.id): job for job in jobs}
        start = (page - 1) * page_size
        items = []
        for row in rows[start:start + page_size]:
            base = JobResponse.model_validate(jobs_by_id[row["id"]])
            items.append(
                CandidateJobRecommendationItem(
                    **base.model_dump(),
                    recommendation_rank=row["rank"],
                    recommendation_status=JobRecommendationStatus(row["status"]),
                    reasons=[JobRecommendationReason.model_validate(reason) for reason in row["reasons"]],
                )
            )
        counts = {
            state: sum(row["status"] == state for row in rows)
            for state in ("ranked", "pending", "unavailable", "error")
        }
        logger.info(
            "Candidate recommendation eligible_job_count=%d cached_ranked_count=%d "
            "pending_embedding_count=%d unavailable_count=%d error_count=%d "
            "candidate_signal_status=%s ranking_duration_ms=%.3f snapshot_reused=%s",
            len(jobs), counts["ranked"], counts["pending"], counts["unavailable"],
            counts["error"], payload["candidate_signal_status"],
            (time.perf_counter() - started) * 1000, snapshot_reused,
        )
        return CandidateJobRecommendationListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=len(rows),
            total_pages=math.ceil(len(rows) / page_size),
            ranking_snapshot=snapshot,
            selected_cv_id=payload["selected_cv_id"],
            candidate_signal_status=JobRecommendationStatus(payload["candidate_signal_status"]),
            ranked_count=counts["ranked"],
            pending_count=counts["pending"],
            unavailable_count=counts["unavailable"],
            error_count=counts["error"],
        )

    def _select_cv(self, candidate_id, explicit_cv_id):
        cvs = self.cv_repository.list_for_candidate(candidate_id)
        if explicit_cv_id is not None:
            selected = next((cv for cv in cvs if cv.id == explicit_cv_id), None)
            if selected is None:
                # Ownership-safe: a foreign and a missing CV have the same response.
                raise HTTPException(404, "CV not found.")
            considered = [selected]
        else:
            considered = cvs

        cv_inputs = self.inputs.build_cv_inputs(considered)
        for cv in considered:
            value = cv_inputs[cv.id]
            if not isinstance(value, Exception) and value.semantic_text.strip():
                return cvs, cv, value, "ranked", cv_inputs

        if explicit_cv_id is not None:
            value = cv_inputs[explicit_cv_id]
            state = (
                "unavailable"
                if not isinstance(value, Exception) or isinstance(value, CVNotReadyForMatchingError)
                else "error"
            )
            return cvs, considered[0], None, state, cv_inputs
        state = "error" if any(
            isinstance(value, Exception) and not isinstance(value, CVNotReadyForMatchingError)
            for value in cv_inputs.values()
        ) else "unavailable"
        return cvs, None, None, state, cv_inputs

    @staticmethod
    def _identity(kind, value):
        return type(value).__name__ if isinstance(value, Exception) else entity_identity(kind, value)

    def _binding(
        self, candidate_id, explicit_cv_id, cvs, selected_cv, cv_input, cv_inputs,
        filters, page_size, jobs, job_inputs,
    ):
        automatic_context = []
        if explicit_cv_id is None:
            for cv in cvs:
                value = cv_inputs.get(cv.id)
                automatic_context.append([
                    str(cv.id), cv.is_default, cv.updated_at.isoformat(),
                    self._identity("cv", value) if value is not None else "not_considered",
                ])
        return digest({
            "policy": RECOMMENDATION_POLICY_VERSION,
            "candidate_id": str(candidate_id),
            "requested_cv_id": str(explicit_cv_id) if explicit_cv_id else None,
            "selected_cv_id": str(selected_cv.id) if selected_cv else None,
            "selected_cv": (
                self._identity("cv", cv_inputs[selected_cv.id]) if selected_cv else None
            ),
            "automatic_cv_context": automatic_context,
            "filters": normalize_recommendation_filters(filters),
            "page_size": page_size,
            "runtime": runtime_identity(),
            "eligibility": "approved-and-never-applied-v1",
            "jobs": [[
                str(job.id), job.status.value, job.created_at.isoformat(), job.updated_at.isoformat(),
                self._identity("job", job_inputs[job.id]),
            ] for job in jobs],
        })

    def _rank(self, jobs, job_inputs, cv_input, selected_cv, selection_state):
        if cv_input is not None:
            candidate_status, candidate_vector = self.cache.vector("cv", cv_input)
        else:
            candidate_status, candidate_vector = selection_state, None

        rows = []
        for job in jobs:
            job_input = job_inputs[job.id]
            score = None
            if candidate_status != "ranked":
                # A job cannot be scored until the selected candidate signal is
                # usable. Avoid irrelevant job-cache reads in that state.
                state = candidate_status
            else:
                job_status, job_vector = self._vector("job", job_input)
                if job_status != "ranked":
                    state = job_status
                else:
                    try:
                        score = cosine_similarity(candidate_vector, job_vector)
                        state = "ranked"
                    except Exception:
                        state = "error"
            reasons = self._reasons(cv_input, job_input) if state == "ranked" else []
            rows.append({
                "id": str(job.id), "status": state, "score": score,
                "rank": None, "reasons": reasons,
            })

        # `jobs` is already newest/id DESC. Python's stable sort preserves that
        # deterministic policy for equal scores and every unranked state.
        rows.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0)))
        rank = 0
        for row in rows:
            if row["status"] == "ranked":
                rank += 1
                row["rank"] = rank
        return {
            "rows": rows,
            "selected_cv_id": str(selected_cv.id) if selected_cv else None,
            "candidate_signal_status": candidate_status,
        }

    def _vector(self, kind, value):
        if isinstance(value, CVNotReadyForMatchingError):
            return "unavailable", None
        if isinstance(value, Exception):
            return "error", None
        return self.cache.vector(kind, value)

    @staticmethod
    def _reasons(cv_input, job_input):
        if cv_input is None or isinstance(job_input, Exception):
            return []
        cv_skills = {skill.normalized_name: skill.name for skill in cv_input.skills}
        for project in cv_input.projects:
            for technology in project.technologies:
                cv_skills.setdefault(technology.normalized_name, technology.name)
        job_skills = {skill.normalized_name: skill.name for skill in job_input.skills}
        shared = sorted(set(cv_skills) & set(job_skills))[:3]
        return [{
            "code": JobRecommendationReasonCode.shared_skill.value,
            "message": f"Kỹ năng {job_skills[key]} xuất hiện trong cả CV và yêu cầu công việc.",
            "evidence": [job_skills[key]],
        } for key in shared]

    def _valid_snapshot_payload(
        self, payload, jobs, job_inputs, cv_input, selected_cv
    ):
        if not isinstance(payload, dict) or set(payload) != {
            "rows", "selected_cv_id", "candidate_signal_status"
        }:
            return False
        expected_cv_id = str(selected_cv.id) if selected_cv else None
        if payload["selected_cv_id"] != expected_cv_id:
            return False
        try:
            candidate_state = JobRecommendationStatus(payload["candidate_signal_status"])
        except (TypeError, ValueError):
            return False

        rows = payload["rows"]
        order = {str(job.id): index for index, job in enumerate(jobs)}
        if not isinstance(rows, list) or len(rows) != len(jobs):
            return False
        seen = set()
        try:
            ranked_count = 0
            for row in rows:
                if not isinstance(row, dict) or set(row) != {"id", "status", "score", "rank", "reasons"}:
                    return False
                if row["id"] not in order or row["id"] in seen:
                    return False
                seen.add(row["id"])
                state = JobRecommendationStatus(row["status"])
                score, rank = row["score"], row["rank"]
                if state == JobRecommendationStatus.ranked:
                    ranked_count += 1
                    if (
                        isinstance(score, bool) or not isinstance(score, (float, int))
                        or not math.isfinite(score) or not -1 <= score <= 1
                        or isinstance(rank, bool) or rank != ranked_count
                    ):
                        return False
                    job_input = job_inputs[uuid.UUID(row["id"])]
                    if row["reasons"] != self._reasons(cv_input, job_input):
                        return False
                elif score is not None or rank is not None or row["reasons"]:
                    return False
                if candidate_state != JobRecommendationStatus.ranked and state != candidate_state:
                    return False
            ordered = sorted(
                rows,
                key=lambda row: (
                    row["score"] is None,
                    -(row["score"] or 0),
                    order[row["id"]],
                ),
            )
            return [row["id"] for row in ordered] == [row["id"] for row in rows]
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
