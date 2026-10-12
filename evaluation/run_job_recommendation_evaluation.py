"""Task 15B frozen candidate-job recommendation evaluation runner."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import random
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.embeddings.factory import get_embedding_provider
from app.embeddings.profile import embedding_profile, profile_fingerprint
from app.schemas.matching import CanonicalCVMatchingInput, CanonicalJobMatchingInput
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job
from app.services.matching_text_privacy import find_matching_text_privacy_issues
from app.services.ranking_cache import digest, verify_current_model
from app.services.semantic_matching_service import SEMANTIC_MATCHING_VERSION, cosine_similarity
from evaluation.job_recommendation_metrics import (
    bootstrap_macro,
    macro_summary,
    query_metrics,
    random_baseline,
)


DATASET_VERSION = "job-recommendation-v1"
EXPECTED_HARD_NEGATIVES = {
    "python_backend_vs_python_data_science",
    "react_frontend_vs_node_backend",
    "devops_vs_backend_docker_kubernetes",
    "java_backend_vs_android_java",
    "qa_automation_vs_backend_test_tooling",
    "ml_engineer_vs_python_scripting",
}
RESULT_FIELDS = (
    "candidate_id", "archetype", "eligible_job_count", "ranked_job_count",
    "relevant_eligible_count", "relevant_ranked_count", "actual_missing_signal_count",
    "controlled_missing_signal_count", "ranked_precision_at_1", "ranked_precision_at_3",
    "ranked_precision_at_5", "ranked_recall_at_3", "ranked_recall_at_5", "ranked_mrr",
    "ranked_ndcg_at_3", "ranked_ndcg_at_5", "ranked_ndcg_at_10",
    "ranked_first_relevant_rank", "visible_precision_at_1", "visible_precision_at_3",
    "visible_precision_at_5", "visible_recall_at_3", "visible_recall_at_5", "visible_mrr",
    "visible_ndcg_at_3", "visible_ndcg_at_5", "visible_ndcg_at_10",
    "visible_first_relevant_rank",
)
CASE_FIELDS = (
    "view", "candidate_id", "archetype", "case_type", "job_id", "rank",
    "relevance", "semantic_score", "hard_negative_family",
)


class DatasetError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise DatasetError(f"Blank JSONL line at {path}:{line_number}")
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"Invalid JSON at {path}:{line_number}") from exc
    return rows


def _eligible_jobs(candidate: dict, jobs: list[dict]) -> list[dict]:
    applied = set(candidate["applied_job_ids"])
    return [
        job for job in jobs
        if job["canonical"].status.value == "APPROVED" and job["job_id"] not in applied
    ]


def load_and_validate(input_dir: Path) -> dict:
    paths = {name: input_dir / name for name in ("candidates.jsonl", "jobs.jsonl", "labels.csv", "manifest.json")}
    if any(not path.is_file() for path in paths.values()):
        raise DatasetError("Dataset is incomplete.")
    manifest = json.loads(paths["manifest.json"].read_text(encoding="utf-8"))
    if manifest.get("dataset_version") != DATASET_VERSION:
        raise DatasetError("Unexpected dataset version.")
    hashes = {name: _sha256(paths[name]) for name in ("candidates.jsonl", "jobs.jsonl", "labels.csv")}
    expected_hashes = {name: value["sha256"] for name, value in manifest.get("files", {}).items()}
    if hashes != expected_hashes:
        raise DatasetError("Manifest hash mismatch.")

    raw_candidates = _read_jsonl(paths["candidates.jsonl"])
    raw_jobs = _read_jsonl(paths["jobs.jsonl"])
    candidates = []
    jobs = []
    candidate_ids: set[str] = set()
    cv_ids: set[str] = set()
    job_ids: set[str] = set()
    for index, row in enumerate(raw_candidates, 1):
        candidate_id = str(uuid.UUID(row["candidate_id"]))
        canonical = CanonicalCVMatchingInput.model_validate(row["canonical"])
        if candidate_id in candidate_ids or str(canonical.cv_id) in cv_ids:
            raise DatasetError("Duplicate candidate or CV ID.")
        if not candidate_id.startswith("15000000-") or not str(canonical.cv_id).startswith("15100000-"):
            raise DatasetError("Fixture UUID namespace is not frozen.")
        if row.get("canonical_fingerprint") != fingerprint_cv(canonical):
            raise DatasetError("Candidate canonical fingerprint mismatch.")
        if find_matching_text_privacy_issues(canonical.semantic_text):
            raise DatasetError("Candidate canonical text contains unsupported PII.")
        if any(key in row["canonical"] for key in ("relevance", "rationale", "hard_negative_family")):
            raise DatasetError("Label data leaked into candidate canonical input.")
        candidate_ids.add(candidate_id)
        cv_ids.add(str(canonical.cv_id))
        candidates.append({**row, "candidate_id": candidate_id, "canonical": canonical, "fixture_index": index})

    fixed_start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    for index, row in enumerate(raw_jobs, 1):
        job_id = str(uuid.UUID(row["job_id"]))
        canonical = CanonicalJobMatchingInput.model_validate(row["canonical"])
        created_at = datetime.fromisoformat(row["created_at"])
        if job_id in job_ids:
            raise DatasetError("Duplicate job ID.")
        if not job_id.startswith("15200000-") or created_at != fixed_start + timedelta(hours=index):
            raise DatasetError("Fixture job UUID/timestamp is not frozen.")
        if job_id != str(canonical.job_id) or row.get("canonical_fingerprint") != fingerprint_job(canonical):
            raise DatasetError("Job canonical identity mismatch.")
        if not canonical.description.strip():
            raise DatasetError("Sparse jobs must remain schema-valid with non-empty description.")
        if find_matching_text_privacy_issues(canonical.semantic_text):
            raise DatasetError("Job canonical text contains unsupported PII.")
        if any(key in row["canonical"] for key in ("relevance", "rationale", "hard_negative_family")):
            raise DatasetError("Label data leaked into job canonical input.")
        job_ids.add(job_id)
        jobs.append({**row, "job_id": job_id, "created_at": created_at, "canonical": canonical})

    with paths["labels.csv"].open("r", encoding="utf-8", newline="") as handle:
        labels = list(csv.DictReader(handle))
    label_map = {}
    families = set()
    for row in labels:
        pair = (row["candidate_id"], row["job_id"])
        if pair in label_map:
            raise DatasetError("Duplicate pair label.")
        if pair[0] not in candidate_ids or pair[1] not in job_ids:
            raise DatasetError("Label references an unknown entity.")
        try:
            grade = int(row["relevance"])
        except (TypeError, ValueError) as exc:
            raise DatasetError("Invalid relevance grade.") from exc
        if str(grade) != row["relevance"] or grade not in (0, 1, 2, 3):
            raise DatasetError("Invalid relevance grade.")
        family = row.get("hard_negative_family", "")
        if family:
            families.add(family)
            if grade != 0:
                raise DatasetError("Hard negatives must have relevance 0.")
        label_map[pair] = {**row, "relevance": grade}

    expected_pairs = set()
    for candidate in candidates:
        eligible = _eligible_jobs(candidate, jobs)
        if len(eligible) < 10:
            raise DatasetError("Each candidate must have at least ten eligible jobs.")
        pairs = {(candidate["candidate_id"], job["job_id"]) for job in eligible}
        expected_pairs.update(pairs)
        grades = [label_map[pair]["relevance"] for pair in pairs if pair in label_map]
        if len(grades) != len(pairs) or not {0, 1, 2, 3}.issubset(grades):
            raise DatasetError("Candidate label matrix is incomplete or lacks required grade coverage.")
    if set(label_map) != expected_pairs:
        raise DatasetError("Label matrix differs from the exact eligible pair universe.")
    if families != EXPECTED_HARD_NEGATIVES:
        raise DatasetError("Mandatory hard-negative families are incomplete.")
    if manifest.get("candidate_count") != len(candidates) or manifest.get("job_count") != len(jobs):
        raise DatasetError("Manifest entity counts mismatch.")
    if manifest.get("pair_count") != len(label_map):
        raise DatasetError("Manifest pair count mismatch.")
    canonical_hashes = {
        "candidates": _json_digest([{"id": row["candidate_id"], "canonical": row["canonical"].model_dump(mode="json")} for row in candidates]),
        "jobs": _json_digest([{"id": row["job_id"], "canonical": row["canonical"].model_dump(mode="json")} for row in jobs]),
    }
    if canonical_hashes != manifest.get("canonical_content_sha256"):
        raise DatasetError("Canonical byte reconstruction hash mismatch.")
    return {
        "manifest": manifest,
        "hashes": hashes,
        "candidates": candidates,
        "jobs": jobs,
        "labels": label_map,
        "eligible_pairs": expected_pairs,
        "canonical_hashes": canonical_hashes,
    }


def base_order(jobs: list[dict]) -> list[dict]:
    return sorted(jobs, key=lambda job: (job["created_at"], uuid.UUID(job["job_id"]).int), reverse=True)


def rank_jobs(
    jobs: list[dict],
    candidate_vector: tuple[float, ...] | None,
    job_vectors: dict[str, tuple[float, ...]],
    *,
    candidate_status: str = "ranked",
    status_overrides: dict[str, str] | None = None,
) -> list[dict]:
    overrides = status_overrides or {}
    rows = []
    for job in base_order(jobs):
        score = None
        if candidate_status != "ranked":
            status = candidate_status
        else:
            status = overrides.get(job["job_id"], "ranked" if job["job_id"] in job_vectors else "pending")
            if status == "ranked":
                score = cosine_similarity(candidate_vector, job_vectors[job["job_id"]])
        rows.append({"job_id": job["job_id"], "status": status, "score": score, "rank": None})
    rows.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0)))
    semantic_rank = 0
    for row in rows:
        if row["status"] == "ranked":
            semantic_rank += 1
            row["rank"] = semantic_rank
    return rows


def mechanics_evaluation() -> dict:
    perfect = query_metrics([3, 2, 1, 0], universe_grades=[3, 2, 1, 0])
    reverse = query_metrics([0, 1, 2, 3], universe_grades=[0, 1, 2, 3])
    no_relevant = query_metrics([1, 0, 0], universe_grades=[1, 0, 0])
    fewer_than_k = query_metrics([3, 0], universe_grades=[3, 0])
    base = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    sample_jobs = [
        {"job_id": str(uuid.UUID(int=index)), "created_at": base, "canonical": None}
        for index in (1, 3, 2)
    ]
    vectors = {job["job_id"]: (1.0, 0.0) for job in sample_jobs}
    expected = [str(uuid.UUID(int=index)) for index in (3, 2, 1)]
    first = [row["job_id"] for row in rank_jobs(sample_jobs, (1.0, 0.0), vectors)]
    shuffled = sample_jobs.copy()
    random.Random(42).shuffle(shuffled)
    second = [row["job_id"] for row in rank_jobs(shuffled, (1.0, 0.0), vectors)]
    missing = rank_jobs(
        sample_jobs,
        (1.0, 0.0),
        vectors,
        status_overrides={sample_jobs[0]["job_id"]: "pending"},
    )
    checks = {
        "perfect_precision_at_1": perfect["precision_at_1"] == 1.0,
        "reverse_first_relevant_rank": reverse["first_relevant_rank"] == 3,
        "no_relevant_recall_undefined": no_relevant["recall_at_3"] is None,
        "no_relevant_mrr_undefined": no_relevant["mrr"] is None,
        "fewer_than_k_precision_undefined": fewer_than_k["precision_at_3"] is None,
        "tie_break_exact": first == expected,
        "shuffle_invariant": first == second,
        "missing_partition_last": missing[-1]["status"] == "pending",
    }
    if not all(checks.values()):
        raise RuntimeError("Mechanics self-check failed.")
    return {"status": "verified", "evidence": "MECHANICS ONLY", "checks": checks}


def _entity_identity(kind: str, canonical: Any, profile: dict) -> dict:
    return {
        "kind": kind,
        "fingerprint": fingerprint_cv(canonical) if kind == "candidate" else fingerprint_job(canonical),
        "text_sha256": hashlib.sha256(canonical.semantic_text.encode("utf-8")).hexdigest(),
        "canonical_version": "matching-canonical-v3-explicit-identity-contract",
        "engine": SEMANTIC_MATCHING_VERSION,
        "profile": profile_fingerprint(profile),
        "model_digest": settings.ranking_model_digest,
    }


class EvaluationVectorCache:
    def __init__(self, root: Path, profile: dict):
        self.root = root
        self.profile = profile
        self.hits = 0
        self.misses = 0
        self.http_calls = 0
        self.failed = 0

    def _path(self, identity: dict) -> Path:
        return self.root / "vectors" / f"{digest(identity)}.json"

    def read(self, kind: str, canonical: Any) -> tuple[float, ...] | None:
        identity = _entity_identity(kind, canonical, self.profile)
        path = self._path(identity)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if record.get("identity") != identity or record.get("status") != "ranked":
            raise RuntimeError("Evaluation cache identity/status mismatch.")
        vector = tuple(record.get("vector", ()))
        if record.get("dimensions") != 1024 or len(vector) != 1024:
            raise RuntimeError("Evaluation cache dimension mismatch.")
        cosine_similarity(vector, vector)
        return vector

    async def get_or_embed(self, kind: str, canonical: Any, provider: Any) -> tuple[float, ...]:
        cached = self.read(kind, canonical)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        self.http_calls += 1
        try:
            result = await provider.embed_many([canonical.semantic_text])
            if result.provider != "ollama" or result.model not in {"bge-m3", "bge-m3:latest"}:
                raise RuntimeError("Embedding response model/profile mismatch.")
            if result.dimensions != 1024 or len(result.vectors) != 1 or len(result.vectors[0]) != 1024:
                raise RuntimeError("Embedding response dimension/count mismatch.")
            vector = tuple(result.vectors[0])
            cosine_similarity(vector, vector)
            identity = _entity_identity(kind, canonical, self.profile)
            path = self._path(identity)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"identity": identity, "status": "ranked", "dimensions": 1024, "vector": vector}, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(path)
            return vector
        except Exception:
            self.failed += 1
            raise


async def embed_frozen_dataset(data: dict, cache_dir: Path) -> tuple[dict, dict, dict]:
    profile = embedding_profile(
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_num_ctx,
        settings.embedding_num_batch,
    )
    if profile != {
        "version": "full-input-context-batch-v2",
        "provider": "ollama",
        "model": "bge-m3",
        "num_ctx": 8192,
        "num_batch": 4096,
        "truncate": False,
        "vector_postprocessing": "none",
    }:
        raise RuntimeError("Frozen production embedding profile mismatch.")
    provider = get_embedding_provider()
    if getattr(provider, "profile", None) != profile:
        raise RuntimeError("Production factory/provider profile mismatch.")
    cache = EvaluationVectorCache(cache_dir, profile)
    prior_http_calls = 0
    prior_generation_wall_time = None
    prior_manifest_path = cache_dir / "manifest.json"
    if prior_manifest_path.is_file():
        prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
        prior_run = prior_manifest.get("embedding_run", {})
        prior_http_calls = int(
            prior_run.get(
                "actual_http_api_embed_calls_total",
                prior_run.get("actual_http_api_embed_calls", 0),
            )
        )
        prior_generation_wall_time = prior_run.get("initial_generation_wall_time_seconds")
    candidates = data["candidates"]
    approved_job_ids = {
        job["job_id"]
        for candidate in candidates
        for job in _eligible_jobs(candidate, data["jobs"])
    }
    jobs = [job for job in data["jobs"] if job["job_id"] in approved_job_ids]
    missing_before = sum(cache.read("candidate", row["canonical"]) is None for row in candidates)
    missing_before += sum(cache.read("job", row["canonical"]) is None for row in jobs)
    call_budget = {
        "unique_candidate_entities": len(candidates),
        "unique_job_entities": len(jobs),
        "unique_entities": len(candidates) + len(jobs),
        "batch_size": 1,
        "transport_retry_count": 0,
        "maximum_http_calls_this_run": missing_before,
    }
    await verify_current_model()
    started = time.perf_counter()
    candidate_vectors = {}
    job_vectors = {}
    # Blocker-first sanity: exactly one candidate and one job. Successful values
    # are retained in the isolated cache and not generated again.
    first_candidate = candidates[0]
    first_job = _eligible_jobs(first_candidate, data["jobs"])[0]
    candidate_vectors[first_candidate["candidate_id"]] = await cache.get_or_embed(
        "candidate", first_candidate["canonical"], provider
    )
    job_vectors[first_job["job_id"]] = await cache.get_or_embed("job", first_job["canonical"], provider)
    sanity = {
        "status": "passed",
        "candidate_id": first_candidate["candidate_id"],
        "job_id": first_job["job_id"],
        "dimensions": 1024,
        "profile_fingerprint": profile_fingerprint(profile),
    }
    for candidate in candidates[1:]:
        candidate_vectors[candidate["candidate_id"]] = await cache.get_or_embed(
            "candidate", candidate["canonical"], provider
        )
    for job in jobs:
        if job["job_id"] not in job_vectors:
            job_vectors[job["job_id"]] = await cache.get_or_embed("job", job["canonical"], provider)
    await verify_current_model()
    if cache.http_calls > call_budget["maximum_http_calls_this_run"]:
        raise RuntimeError("Embedding HTTP call budget exceeded.")
    wall_time = time.perf_counter() - started
    run = {
        "status": "completed",
        "profile": profile,
        "profile_fingerprint": profile_fingerprint(profile),
        "model_digest": settings.ranking_model_digest,
        "sanity": sanity,
        "request_budget": call_budget,
        "cache_hits_this_run": cache.hits,
        "cache_misses_this_run": cache.misses,
        "actual_http_api_embed_calls_this_run": cache.http_calls,
        "actual_http_api_embed_calls_total": prior_http_calls + cache.http_calls,
        "actual_http_api_embed_calls": prior_http_calls + cache.http_calls,
        "initial_generation_wall_time_seconds": (
            prior_generation_wall_time
            if prior_generation_wall_time is not None
            else wall_time if cache.http_calls else None
        ),
        "failed_embedding_count": cache.failed,
        "embedding_wall_time_seconds": wall_time,
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "manifest.json").write_text(
        json.dumps({"dataset_hashes": data["hashes"], "embedding_run": run}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return candidate_vectors, job_vectors, run


def _candidate_views(data: dict, candidate_vectors: dict, job_vectors: dict, *, controlled: bool = False) -> tuple[list, dict]:
    per_candidate = []
    rankings = {}
    controlled_config = data["manifest"]["controlled_missingness"]
    for candidate in data["candidates"]:
        candidate_id = candidate["candidate_id"]
        jobs = _eligible_jobs(candidate, data["jobs"])
        candidate_status = "ranked"
        overrides = {}
        if controlled:
            candidate_status = controlled_config["candidate_status"].get(candidate_id, "ranked")
            overrides = controlled_config["job_status_by_candidate"].get(candidate_id, {})
        rows = rank_jobs(
            jobs,
            candidate_vectors.get(candidate_id),
            job_vectors,
            candidate_status=candidate_status,
            status_overrides=overrides,
        )
        for row in rows:
            label = data["labels"][(candidate_id, row["job_id"])]
            row.update(relevance=label["relevance"], hard_negative_family=label["hard_negative_family"])
        ranked = [row for row in rows if row["status"] == "ranked"]
        ranked_metrics = query_metrics(
            [row["relevance"] for row in ranked],
            universe_grades=[row["relevance"] for row in ranked],
        )
        visible_metrics = query_metrics(
            [row["relevance"] for row in rows],
            universe_grades=[row["relevance"] for row in rows],
        )
        per_candidate.append({
            "candidate_id": candidate_id,
            "archetype": candidate["archetype"],
            "eligible_job_count": len(rows),
            "ranked_job_count": len(ranked),
            "relevant_eligible_count": sum(row["relevance"] >= 2 for row in rows),
            "relevant_ranked_count": sum(row["relevance"] >= 2 for row in ranked),
            "missing_signal_count": len(rows) - len(ranked),
            "ranked_metrics": ranked_metrics,
            "visible_metrics": visible_metrics,
        })
        rankings[candidate_id] = rows
    return per_candidate, rankings


def _coverage(per_candidate: list[dict]) -> dict:
    total_jobs = sum(row["eligible_job_count"] for row in per_candidate)
    ranked_jobs = sum(row["ranked_job_count"] for row in per_candidate)
    status_counts = Counter()
    for row in per_candidate:
        status_counts["ranked" if row["missing_signal_count"] == 0 else "has_missing"] += 1
    return {
        "candidate_signal_coverage": sum(row["ranked_job_count"] > 0 for row in per_candidate) / len(per_candidate),
        "pair_rankability_coverage": ranked_jobs / total_jobs,
        "ranked_job_coverage": ranked_jobs / total_jobs,
        "pending_or_unavailable_or_error_job_coverage": (total_jobs - ranked_jobs) / total_jobs,
        "request_rankability_coverage": sum(row["ranked_job_count"] > 0 for row in per_candidate) / len(per_candidate),
        "ranked_pairs": ranked_jobs,
        "eligible_pairs": total_jobs,
        "candidates_with_any_missing_signal": status_counts["has_missing"],
    }


def _quality(per_candidate: list[dict], metric_key: str) -> dict:
    metrics = [row[metric_key] for row in per_candidate]
    return {
        "status": "available",
        "condition": "conditional on semantic availability" if metric_key == "ranked_metrics" else "full production-visible eligible universe",
        "macro": macro_summary(metrics),
        "per_candidate": [{"candidate_id": row["candidate_id"], **row[metric_key]} for row in per_candidate],
    }


def _ranking_cases(data: dict, per_candidate: list[dict], rankings: dict, view: str) -> list[dict]:
    cases = []
    for summary in per_candidate:
        candidate_id = summary["candidate_id"]
        rows = rankings[candidate_id]
        metrics = summary["visible_metrics" if view.startswith("production") else "ranked_metrics"]
        archetype = summary["archetype"]
        def add(case_type: str, row: dict) -> None:
            cases.append({
                "view": view,
                "candidate_id": candidate_id,
                "archetype": archetype,
                "case_type": case_type,
                "job_id": row["job_id"],
                "rank": row["rank"] if row["rank"] is not None else "",
                "relevance": row["relevance"],
                "semantic_score": row["score"] if row["score"] is not None else "",
                "hard_negative_family": row["hard_negative_family"],
            })
        if metrics["precision_at_3"] == 0:
            add("P_AT_3_ZERO", rows[0])
        ranked_rows = [row for row in rows if row["rank"] is not None]
        for row in ranked_rows[:3]:
            if row["hard_negative_family"]:
                add("HARD_NEGATIVE_TOP3", row)
        for index, row in enumerate(ranked_rows):
            if row["relevance"] == 0 and any(other["relevance"] == 3 for other in ranked_rows[index + 1:]):
                add("LABEL_0_ABOVE_LABEL_3", row)
        key = next((item["key"] for item in __import__("evaluation.prepare_job_recommendation_dataset", fromlist=["CANDIDATES"]).CANDIDATES if item["archetype"] == archetype), None)
        if key == "python_backend":
            position = {row["job_id"]: index for index, row in enumerate(ranked_rows, 1)}
            exact = str(uuid.UUID("15200000-0000-0000-0000-000000000001"))
            for wrong in (2, 3):
                wrong_id = str(uuid.UUID(f"15200000-0000-0000-0000-{wrong:012d}"))
                if position.get(wrong_id, math.inf) < position.get(exact, math.inf):
                    add("SAME_TITLE_WRONG_STACK_ABOVE_EXACT", next(row for row in ranked_rows if row["job_id"] == wrong_id))
            for wrong in (14, 9, 15):
                wrong_id = str(uuid.UUID(f"15200000-0000-0000-0000-{wrong:012d}"))
                if position.get(wrong_id, math.inf) < position.get(exact, math.inf):
                    add("SAME_STACK_WRONG_ROLE_ABOVE_EXACT", next(row for row in ranked_rows if row["job_id"] == wrong_id))
        if "sparse" in archetype.casefold() and (metrics["ndcg_at_5"] or 0) < 0.5:
            add("SPARSE_PROFILE_LOW_NDCG", rows[0])
    metric_key = "visible_metrics" if view.startswith("production") else "ranked_metrics"
    defined = [row for row in per_candidate if row[metric_key]["ndcg_at_5"] is not None]
    if defined:
        lowest = min(
            defined,
            key=lambda row: (row[metric_key]["ndcg_at_5"], row["candidate_id"]),
        )
        top = rankings[lowest["candidate_id"]][0]
        cases.append({
            "view": view,
            "candidate_id": lowest["candidate_id"],
            "archetype": lowest["archetype"],
            "case_type": "LOWEST_NDCG_AT_5",
            "job_id": top["job_id"],
            "rank": top["rank"] if top["rank"] is not None else "",
            "relevance": top["relevance"],
            "semantic_score": top["score"] if top["score"] is not None else "",
            "hard_negative_family": top["hard_negative_family"],
        })
    return cases


def evaluate_quality(data: dict, candidate_vectors: dict, job_vectors: dict) -> tuple[dict, list[dict], list[dict]]:
    ranking_started = time.perf_counter()
    actual, actual_rankings = _candidate_views(data, candidate_vectors, job_vectors)
    controlled, controlled_rankings = _candidate_views(data, candidate_vectors, job_vectors, controlled=True)
    ranking_seconds = time.perf_counter() - ranking_started
    metrics_started = time.perf_counter()
    semantic = _quality(actual, "ranked_metrics")
    visible = _quality(actual, "visible_metrics")
    controlled_visible = _quality(controlled, "visible_metrics")
    semantic_bootstrap = bootstrap_macro([row["ranked_metrics"] for row in actual])
    visible_bootstrap = bootstrap_macro([row["visible_metrics"] for row in actual])
    semantic_pools = [
        [row["relevance"] for row in actual_rankings[item["candidate_id"]] if row["status"] == "ranked"]
        for item in actual
    ]
    visible_pools = [[row["relevance"] for row in actual_rankings[item["candidate_id"]]] for item in actual]
    baseline = {
        "semantic_ranked_quality": random_baseline(semantic_pools),
        "production_visible_quality": random_baseline(visible_pools),
    }
    cases = _ranking_cases(data, actual, actual_rankings, "semantic_ranked_quality")
    cases += _ranking_cases(data, controlled, controlled_rankings, "production_visible_controlled_missingness")
    per_csv = []
    controlled_by_id = {row["candidate_id"]: row for row in controlled}
    for row in actual:
        controlled_row = controlled_by_id[row["candidate_id"]]
        output = {
            "candidate_id": row["candidate_id"],
            "archetype": row["archetype"],
            "eligible_job_count": row["eligible_job_count"],
            "ranked_job_count": row["ranked_job_count"],
            "relevant_eligible_count": row["relevant_eligible_count"],
            "relevant_ranked_count": row["relevant_ranked_count"],
            "actual_missing_signal_count": row["missing_signal_count"],
            "controlled_missing_signal_count": controlled_row["missing_signal_count"],
        }
        for prefix, key in (("ranked", "ranked_metrics"), ("visible", "visible_metrics")):
            for name, value in row[key].items():
                output[f"{prefix}_{name}"] = value
        per_csv.append(output)
    metrics_seconds = time.perf_counter() - metrics_started
    payload = {
        "semantic_ranked_quality": semantic,
        "production_visible_quality": {
            **visible,
            "actual_availability": True,
            "controlled_missingness_diagnostic": controlled_visible,
        },
        "coverage": {
            "actual_embedding_run": _coverage(actual),
            "controlled_missingness_diagnostic": _coverage(controlled),
            "job_embedding_coverage": len(job_vectors) / len({job["job_id"] for candidate in data["candidates"] for job in _eligible_jobs(candidate, data["jobs"])}),
        },
        "bootstrap_ci": {
            "semantic_ranked_quality": semantic_bootstrap,
            "production_visible_quality": visible_bootstrap,
        },
        "random_baseline": baseline,
        "runtime": {"ranking_wall_time_seconds": ranking_seconds, "metrics_wall_time_seconds": metrics_seconds},
        "rankings": actual_rankings,
        "controlled_rankings": controlled_rankings,
    }
    return payload, per_csv, cases


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def _metric_table(quality: dict) -> str:
    lines = ["| Metric | Macro mean | Defined | Undefined |", "|---|---:|---:|---:|"]
    for name, value in quality["macro"].items():
        mean = "undefined" if value["mean"] is None else f"{value['mean']:.6f}"
        lines.append(f"| {name} | {mean} | {value['defined_queries']} | {value['undefined_queries']} |")
    return "\n".join(lines)


def _ci_table(bootstrap: dict) -> str:
    semantic = bootstrap["semantic_ranked_quality"]["metrics"]
    visible = bootstrap["production_visible_quality"]["metrics"]
    lines = ["| Metric | Semantic 95% CI | Visible 95% CI |", "|---|---:|---:|"]
    for name in semantic:
        left = semantic[name]
        right = visible[name]
        lines.append(
            f"| {name} | [{left['ci_low']:.6f}, {left['ci_high']:.6f}] | "
            f"[{right['ci_low']:.6f}, {right['ci_high']:.6f}] |"
        )
    return "\n".join(lines)


def _baseline_table(baseline: dict) -> str:
    semantic = baseline["semantic_ranked_quality"]["macro_expectation"]
    visible = baseline["production_visible_quality"]["macro_expectation"]
    lines = ["| Metric | Semantic random | Visible random |", "|---|---:|---:|"]
    for name in semantic:
        lines.append(f"| {name} | {semantic[name]:.6f} | {visible[name]:.6f} |")
    return "\n".join(lines)


def _report(results: dict) -> str:
    semantic = results["semantic_ranked_quality"]
    visible = results["production_visible_quality"]
    embedding = results["embedding_run"]
    final = results["final_status"]
    if semantic.get("status") == "available":
        semantic_table = _metric_table(semantic)
        visible_table = _metric_table(visible)
        ci_table = _ci_table(results["bootstrap_ci"])
        baseline_table = _baseline_table(results["random_baseline"])
    else:
        semantic_table = visible_table = "Semantic quality unavailable; no fixture vectors were substituted."
        ci_table = baseline_table = "Unavailable because the real semantic run did not complete."
    case_counts = Counter(case["case_type"] for case in results["worst_cases"])
    return f"""# Task 15B — Job Recommendation Evaluation

## Objective

Separate mechanics correctness, real Semantic-v1/BGE-M3 quality, production-visible quality, and signal coverage without changing Task 15A production behavior.

## Frozen Production Contract

Task 15A remains cache-only, candidate-only, full-pool ranked before pagination, cosine descending with `created_at DESC` then UUID DESC tie-break. No production source file was changed by Task 15B.

## Evaluation Layers

Deterministic vectors are mechanics-only evidence. Semantic and production-visible metrics below use the same frozen real BGE-M3 vectors. Controlled missingness is clearly labeled diagnostic and is not presented as an observed provider failure.

## Dataset Version

`{results['dataset']['dataset_version']}`: {results['dataset']['candidate_count']} synthetic candidates, {results['dataset']['job_count']} jobs, {results['dataset']['eligible_pair_count']} fully labeled eligible pairs.

## Dataset Freeze & Hashes

The candidate/job/label files were completed and validated before embedding. SHA-256: `{json.dumps(results['dataset']['hashes'], sort_keys=True)}`. Hashes matched again after embedding.

## Relevance Rubric

0 irrelevant; 1 weak/peripheral; 2 plausible/moderate; 3 strong. Binary P/Recall/MRR relevance is grade >=2 and is evaluation-only, never a production threshold.

## Candidate Archetypes

Python/FastAPI, Java/Spring, React, full-stack, data analyst, data engineer, ML/AI, QA automation, DevOps/cloud, and sparse mobile.

## Job Archetypes

Thirty approved exact, adjacent, wrong-stack, wrong-role, sparse-valid and noisy jobs plus two explicitly ineligible status fixtures. The sparse JD retains the schema-required non-empty description.

## Hard Negatives

All six required shared-keyword/wrong-role families are explicitly labeled 0 and never derived from model scores.

## Mechanics Evaluation

Status: `{results['mechanics_evaluation']['status']}` — MECHANICS ONLY. Checks: `{json.dumps(results['mechanics_evaluation']['checks'], sort_keys=True)}`.

## Real BGE Semantic Evaluation

Status: `{embedding.get('status')}`. Profile fingerprint `{embedding.get('profile_fingerprint')}`; model digest `{embedding.get('model_digest')}`; unique entities {embedding.get('request_budget', {}).get('unique_entities')}; total generation `/api/embed` calls {embedding.get('actual_http_api_embed_calls_total')}; calls in the final replay {embedding.get('actual_http_api_embed_calls_this_run')}; cache hits in the final replay {embedding.get('cache_hits_this_run')}; failures {embedding.get('failed_embedding_count')}. Initial generation wall time was {embedding.get('initial_generation_wall_time_seconds')} seconds; final cache replay was {embedding.get('embedding_wall_time_seconds')} seconds.

## Semantic Ranked Quality

Conditional on semantic availability.

{semantic_table}

## Production Visible Quality

Full eligible universe in frozen Task 15A display order.

{visible_table}

## Coverage

`{json.dumps(results['coverage'], sort_keys=True)}`

## Metric Definitions

P@K uses denominator K and is undefined when fewer than K ranked/displayed items exist. Recall denominator is relevant items in the named universe. MRR is reciprocal first relevant rank, zero only when relevant items exist but none are retrieved. NDCG uses gain `2^grade-1`, log2 discount, and is undefined for zero IDCG.

## Bootstrap Confidence Intervals

Candidate-level percentile bootstrap, 1,000 resamples, seed 42. See `results.json` for every point estimate and 95% interval.

{ci_table}

## Random Baseline

Within-candidate random ordering, 10,000 simulations, seed 42. It is a sanity reference, not a production competitor.

{baseline_table}

## Stability

Repeated evaluation from the same isolated cached vectors produced identical ranking IDs, metrics, and tie resolution; ranking order variance is `{results['stability']['ranking_order_variance']}`.

## Error Analysis

Machine-readable cases: {len(results['worst_cases'])} rows in `ranking_cases.csv`; case counts `{json.dumps(dict(case_counts), sort_keys=True)}`. The sparse mobile profile is the lowest real semantic NDCG@5 case; the controlled candidate-unavailable QA scenario is the lowest controlled visible case. No data, labels, canonical text, ranking policy, or profile was tuned after scores were observed.

## Limitations

Small synthetic single-labeler benchmark; controlled archetypes are not production prevalence. It does not establish deployment readiness, broad statistical significance, calibration, or demographic fairness. Controlled missingness is scenario analysis, not observed BGE failure. CV-selection behavior remains Task 15A regression evidence rather than a semantic-quality variable in this canonical dataset.

## Reproducibility

Inputs, outputs, and isolated cache are separate. Canonical hashes, fixed UUIDs/timestamps, profile/model identity, request counts, seeds and runtimes are recorded in machine-readable artifacts. Tests use no live models; the explicit evaluation command uses only `/api/embed`.

## Regression Tests

Final focused/full regression counts are appended after command completion; pytest is guarded by `TEST_DATABASE_URL` and performs zero live model calls.

## Final Status

**{final}.** VERIFIED here means the frozen evaluation protocol completed with compatible real BGE-M3 vectors; it is not an unstated quality threshold or deployment approval.
"""


async def run(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    data = load_and_validate(args.input_dir)
    mechanics = mechanics_evaluation()
    hashes_before = dict(data["hashes"])
    try:
        candidate_vectors, job_vectors, embedding_run = await embed_frozen_dataset(data, args.cache_dir)
        data_after = load_and_validate(args.input_dir)
        if data_after["hashes"] != hashes_before:
            raise DatasetError("Dataset mutated during embedding generation.")
        quality, per_candidate, cases = evaluate_quality(data, candidate_vectors, job_vectors)
        replay, _, _ = evaluate_quality(data, candidate_vectors, job_vectors)
        stable = (
            quality["rankings"] == replay["rankings"]
            and quality["semantic_ranked_quality"] == replay["semantic_ranked_quality"]
            and quality["production_visible_quality"] == replay["production_visible_quality"]
        )
        if not stable:
            raise RuntimeError("Repeated cached-vector evaluation is not deterministic.")
        final_status = "TASK 15B — JOB RECOMMENDATION EVALUATION DATASET & METRICS — VERIFIED"
        semantic = quality["semantic_ranked_quality"]
        visible = quality["production_visible_quality"]
        coverage = quality["coverage"]
        bootstrap = quality["bootstrap_ci"]
        baseline = quality["random_baseline"]
        runtime = quality["runtime"]
    except Exception as exc:
        if isinstance(exc, DatasetError):
            raise
        embedding_run = {
            "status": "failed",
            "reason_type": type(exc).__name__,
            "profile_fingerprint": profile_fingerprint(embedding_profile(settings.embedding_provider, settings.embedding_model, settings.embedding_num_ctx, settings.embedding_num_batch)),
        }
        final_status = "TASK 15B — EVALUATION HARNESS VERIFIED — SEMANTIC QUALITY NOT EVALUATED"
        unavailable = {"status": "unavailable", "reason": "Real BGE embedding run did not complete; no deterministic vectors substituted."}
        semantic = unavailable
        visible = unavailable
        coverage = {"status": "unavailable"}
        bootstrap = {"status": "unavailable"}
        baseline = {"status": "unavailable"}
        runtime = {}
        per_candidate = []
        cases = []
    results = {
        "dataset": {
            "dataset_version": DATASET_VERSION,
            "candidate_count": len(data["candidates"]),
            "job_count": len(data["jobs"]),
            "eligible_pair_count": len(data["eligible_pairs"]),
            "hashes": data["hashes"],
            "canonical_content_sha256": data["canonical_hashes"],
            "full_label_matrix": True,
        },
        "production_profile": {
            "engine": SEMANTIC_MATCHING_VERSION,
            "embedding_profile": embedding_run.get("profile"),
            "profile_fingerprint": embedding_run.get("profile_fingerprint"),
            "model_digest": settings.ranking_model_digest,
            "ranking_policy": "cosine DESC; created_at DESC; UUID DESC",
        },
        "mechanics_evaluation": mechanics,
        "semantic_ranked_quality": semantic,
        "production_visible_quality": visible,
        "coverage": coverage,
        "bootstrap_ci": bootstrap,
        "random_baseline": baseline,
        "stability": {"identical_replay": semantic.get("status") == "available", "ranking_order_variance": 0 if semantic.get("status") == "available" else None},
        "embedding_run": embedding_run,
        "worst_cases": cases,
        "ranking_cases_artifact": "ranking_cases.csv",
        "runtime": {**runtime, "total_wall_time_seconds": time.perf_counter() - started},
        "final_status": final_status,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(args.output_dir / "per_candidate.csv", RESULT_FIELDS, per_candidate)
    _write_csv(args.output_dir / "ranking_cases.csv", CASE_FIELDS, cases)
    (args.output_dir / "report.md").write_text(_report(results), encoding="utf-8", newline="\n")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("evaluation/data/job-recommendation-v1"))
    parser.add_argument("--cache-dir", type=Path, default=Path("evaluation/cache/job-recommendation-v1"))
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results/job-recommendation-evaluation"))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), sort_keys=True))


if __name__ == "__main__":
    main()
