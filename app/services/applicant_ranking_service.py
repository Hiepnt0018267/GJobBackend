"""Authorization follows the existing owner query; read-only, cache-only ranking."""
import logging
import math
import time

from fastapi import HTTPException

from app.schemas.recruiter_application import (
    ApplicantRankingMode, ApplicantRankingStatus, RecruiterApplicationListItem, RecruiterApplicationListResponse,
)
from app.services.matching_input_mapper import build_job_matching_input
from app.services.matching_input_service import MatchingInputService, CVNotReadyForMatchingError
from app.services.ranking_cache import RankingCache, digest, entity_identity, runtime_identity
from app.services.semantic_matching_service import cosine_similarity

logger = logging.getLogger(__name__)


class ApplicantRankingService:
    def __init__(self, db, cache=None):
        self.inputs = MatchingInputService(db)
        self.cache = cache or RankingCache()

    def list(self, applications, *, owner, filters, page, page_size, top_n=None, snapshot=None, ranking_mode=None):
        started = time.perf_counter()
        validate_ranking_options(ranking_mode, top_n)
        if len({a.id for a in applications}) != len(applications):
            raise HTTPException(409, "Duplicate application input. Reload the applicant list.")
        cvs = {a.cv_id: a.cv for a in applications}
        cv_inputs = self.inputs.build_cv_inputs(list(cvs.values()))
        jobs = {a.job_id: a.job for a in applications}
        job_inputs = {}
        for key, job in jobs.items():
            try:
                job_inputs[key] = build_job_matching_input(job, [link.skill for link in job.skill_links])
            except (ValueError, TypeError) as exc:
                job_inputs[key] = exc
        # Availability changes do NOT invalidate a traversal snapshot. Source,
        # business membership/status, filters, owner and runtime changes DO.
        def identity(kind, value):
            return type(value).__name__ if isinstance(value, Exception) else entity_identity(kind, value)
        binding = digest({"owner": str(owner), "filters": filters, "page_size": page_size,
            "top_n": top_n, "runtime": runtime_identity(),
            **({"result_contract": "ranked-only-top-n-v1", "ranking_mode": ranking_mode} if ranking_mode else {}),
            "applications": [[str(a.id), str(a.cv_id), str(a.job_id), str(a.candidate_id),
                              str(a.cv.candidate_id), a.status.value,
                              a.created_at.isoformat()] for a in applications],
            "cvs": {str(k): identity("cv", v) for k, v in cv_inputs.items()},
            "jobs": {str(k): identity("job", v) for k, v in job_inputs.items()}})
        if snapshot:
            rows = self.cache.load_snapshot(snapshot, binding)
            if rows is None or not self._valid_snapshot_rows(rows, applications, None if ranking_mode else top_n):
                raise HTTPException(409, "Ranking snapshot expired or inputs changed. Restart at page 1.")
        else:
            if page != 1:
                raise HTTPException(422, "AI pages after page 1 require ranking_snapshot.")
            cv_vectors = {k: self._vector("cv", v) for k, v in cv_inputs.items()}
            job_vectors = {k: self._vector("job", v) for k, v in job_inputs.items()}
            rows = []
            for a in applications:
                cv_status, cv_vector = cv_vectors[a.cv_id]
                job_status, job_vector = job_vectors[a.job_id]
                score = None
                if a.cv.candidate_id != a.candidate_id:
                    state = "error"
                elif "error" in (cv_status, job_status):
                    state = "error"
                elif "unavailable" in (cv_status, job_status):
                    state = "unavailable"
                elif "pending" in (cv_status, job_status):
                    state = "pending"
                else:
                    try:
                        score = cosine_similarity(cv_vector, job_vector)
                        state = "ranked"
                    except Exception:
                        state = "error"
                rows.append({"id": str(a.id), "ranking_status": state,
                             "semantic_match_score": score, "ai_rank": None})
            # Input list already has the exact default DESC created_at/id order.
            # Stable sorting retains that order for ties and non-ranked applicants.
            rows.sort(key=lambda r: (r["semantic_match_score"] is None,
                                     -(r["semantic_match_score"] or 0)))
            for i, row in enumerate(rows, 1):
                if row["ranking_status"] == "ranked":
                    row["ai_rank"] = i
            if top_n is not None and ranking_mode is None:
                rows = rows[:top_n]
            try:
                snapshot = self.cache.save_snapshot(binding, rows)
            except OSError as exc:
                raise HTTPException(503, "Stable AI pagination is temporarily unavailable. Use default sort.") from exc
        # New explicit result contract retains the complete snapshot; only its
        # ranked partition is sliced. Non-ranked rows NEVER fill Top-N slots.
        metadata = {}
        if ranking_mode:
            ranked = [r for r in rows if r["ranking_status"] == "ranked"]
            unranked = [r for r in rows if r["ranking_status"] != "ranked"]
            selected = ranked[:top_n] if ranking_mode == ApplicantRankingMode.top_n else ranked
            metadata = dict(ranking_mode=ranking_mode, requested_top_n=top_n,
                ranked_available_count=len(ranked), returned_ranked_count=len(selected),
                unranked_count=len(unranked))
            rows = selected + unranked
        by_id = {str(a.id): a for a in applications}
        items = []
        for row in rows[(page - 1) * page_size:page * page_size]:
            item = RecruiterApplicationListItem.model_validate(by_id[row["id"]])
            items.append(item.model_copy(update={
                "ai_rank": row["ai_rank"],
                "ranking_status": ApplicantRankingStatus(row["ranking_status"]),
                "semantic_match_score": row["semantic_match_score"],
            }))
        counts = {state: sum(r["ranking_status"] == state for r in rows)
                  for state in ("ranked", "pending", "unavailable", "error")}
        logger.info("Applicant ranking counts=%s total=%d runtime_ms=%.3f", counts, len(applications),
                    (time.perf_counter() - started) * 1000)
        return RecruiterApplicationListResponse(items=items, page=page, page_size=page_size,
            total=len(rows), total_pages=math.ceil(len(rows) / page_size), ranking_snapshot=snapshot, **metadata)

    def _vector(self, kind, value):
        if isinstance(value, CVNotReadyForMatchingError):
            return "unavailable", None
        if isinstance(value, Exception):
            return "error", None
        return self.cache.vector(kind, value)

    @staticmethod
    def _valid_snapshot_rows(rows, applications, top_n):
        """Validate the WHOLE traversal, not just the requested page.

        Private storage corruption must not yield duplicates, omissions, NaN
        ordering or invented ranks. No recomputation of availability/model score.
        """
        order = {str(a.id): i for i, a in enumerate(applications)}
        expected = len(applications) if top_n is None else min(top_n, len(applications))
        if not isinstance(rows, list) or len(rows) != expected:
            return False
        seen = set()
        try:
            for index, row in enumerate(rows, 1):
                if not isinstance(row, dict) or row['id'] not in order or row['id'] in seen:
                    return False
                seen.add(row['id'])
                state = ApplicantRankingStatus(row['ranking_status'])
                score, rank = row['semantic_match_score'], row['ai_rank']
                if state == ApplicantRankingStatus.ranked:
                    if (isinstance(score, bool) or not isinstance(score, (float, int))
                        or not -1 <= score <= 1 or not math.isfinite(score)
                        or isinstance(rank, bool) or not isinstance(rank, int) or rank != index):
                        return False
                elif score is not None or rank is not None:
                    return False
            sorted_rows = sorted(rows, key=lambda r: (r['semantic_match_score'] is None,
                -(r['semantic_match_score'] or 0), order[r['id']]))
            return [r['id'] for r in sorted_rows] == [r['id'] for r in rows]
        except (KeyError, TypeError, ValueError):
            return False


def validate_ranking_options(ranking_mode, top_n):
    """Validate before canonical/cache work; absent mode retains legacy semantics."""
    if ranking_mode is not None and ranking_mode not in (ApplicantRankingMode.all, ApplicantRankingMode.top_n):
        raise HTTPException(422, "Unsupported ranking_mode.")
    if top_n is not None and (isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0):
        raise HTTPException(422, "top_n must be a positive integer.")
    if ranking_mode == ApplicantRankingMode.top_n and top_n is None:
        raise HTTPException(422, "top_n is required for top_n mode.")
    if ranking_mode == ApplicantRankingMode.all and top_n is not None:
        raise HTTPException(422, "all mode does not accept top_n.")
