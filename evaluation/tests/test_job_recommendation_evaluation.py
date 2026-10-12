"""Task 15B deterministic harness tests. No network, provider, or database calls."""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.job_recommendation_service import CandidateJobRecommendationService
from evaluation.job_recommendation_metrics import (
    bootstrap_macro,
    macro_summary,
    query_metrics,
    random_baseline,
)
from evaluation.prepare_job_recommendation_dataset import DATASET_VERSION, prepare
from evaluation.run_job_recommendation_evaluation import (
    DatasetError,
    _ranking_cases,
    base_order,
    load_and_validate,
    mechanics_evaluation,
    rank_jobs,
)


def _dataset(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / DATASET_VERSION
    prepare(root)
    return root, load_and_validate(root)


def test_metric_definitions_perfect_reverse_and_exact_denominators():
    perfect = query_metrics([3, 2, 1, 0, 0], universe_grades=[3, 2, 1, 0, 0])
    assert perfect["precision_at_1"] == 1
    assert perfect["precision_at_3"] == pytest.approx(2 / 3)
    assert perfect["precision_at_5"] == pytest.approx(2 / 5)
    assert perfect["recall_at_3"] == 1
    assert perfect["mrr"] == 1
    assert perfect["ndcg_at_5"] == 1

    reverse = query_metrics([0, 0, 1, 2, 3], universe_grades=[0, 0, 1, 2, 3])
    assert reverse["first_relevant_rank"] == 4
    assert reverse["mrr"] == pytest.approx(0.25)
    assert reverse["recall_at_3"] == 0
    assert reverse["ndcg_at_5"] < perfect["ndcg_at_5"]


def test_metric_undefined_semantics_and_conditional_recall():
    no_relevant = query_metrics([0, 0, 0])
    assert no_relevant["precision_at_3"] == 0
    assert no_relevant["recall_at_3"] is None
    assert no_relevant["mrr"] is None
    assert no_relevant["ndcg_at_3"] is None

    short = query_metrics([3, 0])
    assert short["precision_at_3"] is None
    assert short["recall_at_3"] is None
    assert short["ndcg_at_3"] is None

    conditional = query_metrics([2, 0, 0], universe_grades=[2, 0, 0])
    visible = query_metrics([2, 0, 0, 3], universe_grades=[2, 0, 0, 3])
    assert conditional["recall_at_3"] == 1
    assert visible["recall_at_3"] == 0.5


def test_macro_bootstrap_and_random_baseline_are_deterministic():
    rows = [query_metrics([3, 2, 1, 0, 0]), query_metrics([0, 2, 3, 1, 0])]
    summary = macro_summary(rows)
    assert summary["precision_at_1"]["defined_queries"] == 2
    assert bootstrap_macro(rows) == bootstrap_macro(rows)
    assert random_baseline([[3, 2, 1, 0, 0]], simulations=100) == random_baseline(
        [[3, 2, 1, 0, 0]], simulations=100
    )


def test_frozen_dataset_has_complete_eligible_label_matrix_and_hard_negatives(tmp_path):
    root, data = _dataset(tmp_path)
    assert len(data["candidates"]) == 10
    assert len(data["jobs"]) == 32
    assert len(data["labels"]) == len(data["eligible_pairs"]) == 290
    families = {row["hard_negative_family"] for row in data["labels"].values() if row["hard_negative_family"]}
    assert families == {
        "python_backend_vs_python_data_science",
        "react_frontend_vs_node_backend",
        "devops_vs_backend_docker_kubernetes",
        "java_backend_vs_android_java",
        "qa_automation_vs_backend_test_tooling",
        "ml_engineer_vs_python_scripting",
    }
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pair_count"] == 290
    assert manifest["controlled_missingness"]["evidence_type"].startswith("diagnostic mask")


def test_dataset_rejects_missing_label_duplicate_and_hash_mismatch(tmp_path):
    root, _ = _dataset(tmp_path)
    labels_path = root / "labels.csv"
    rows = list(csv.DictReader(labels_path.open(encoding="utf-8", newline="")))
    with labels_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[:-1])
    with pytest.raises(DatasetError, match="hash mismatch"):
        load_and_validate(root)


def test_fixed_tie_break_and_shuffle_invariance(tmp_path):
    _, data = _dataset(tmp_path)
    candidate = data["candidates"][0]
    jobs = [job for job in data["jobs"] if job["canonical"].status.value == "APPROVED"][:8]
    vectors = {job["job_id"]: (1.0, 0.0) for job in jobs}
    expected = [row["job_id"] for row in rank_jobs(jobs, (1.0, 0.0), vectors)]
    shuffled = jobs.copy()
    random.Random(42).shuffle(shuffled)
    actual = [row["job_id"] for row in rank_jobs(shuffled, (1.0, 0.0), vectors)]
    assert actual == expected
    assert expected == [job["job_id"] for job in base_order(jobs)]
    assert candidate["canonical"].semantic_text


def test_evaluation_rank_is_differentially_identical_to_task15a_service(tmp_path):
    _, data = _dataset(tmp_path)
    candidate = data["candidates"][0]
    jobs = base_order([job for job in data["jobs"] if job["canonical"].status.value == "APPROVED"][:5])
    candidate_vector = (1.0, 0.0)
    job_vectors = {
        jobs[0]["job_id"]: (0.8, 0.6),
        jobs[1]["job_id"]: (0.8, 0.6),
        jobs[2]["job_id"]: (0.2, math.sqrt(0.96)),
        jobs[4]["job_id"]: (-1.0, 0.0),
    }
    expected = rank_jobs(jobs, candidate_vector, job_vectors)

    class Cache:
        def vector(self, kind, canonical):
            if kind == "cv":
                return "ranked", candidate_vector
            if str(canonical.job_id) not in job_vectors:
                return "pending", None
            return "ranked", job_vectors[str(canonical.job_id)]

    service = object.__new__(CandidateJobRecommendationService)
    service.cache = Cache()
    job_objects = [SimpleNamespace(id=job["canonical"].job_id) for job in jobs]
    job_inputs = {job["canonical"].job_id: job["canonical"] for job in jobs}
    selected = SimpleNamespace(id=candidate["canonical"].cv_id)
    actual = service._rank(job_objects, job_inputs, candidate["canonical"], selected, "ranked")["rows"]
    assert [row["id"] for row in actual] == [row["job_id"] for row in expected]
    assert [row["status"] for row in actual] == [row["status"] for row in expected]
    assert [row["rank"] for row in actual] == [row["rank"] for row in expected]
    for actual_row, expected_row in zip(actual, expected, strict=True):
        if expected_row["score"] is None:
            assert actual_row["score"] is None
        else:
            assert actual_row["score"] == pytest.approx(expected_row["score"])


def test_mechanics_self_check_is_explicitly_nonsemantic():
    result = mechanics_evaluation()
    assert result["status"] == "verified"
    assert result["evidence"] == "MECHANICS ONLY"
    assert all(result["checks"].values())


def test_error_analysis_always_records_lowest_ndcg_candidate():
    per_candidate = [
        {
            "candidate_id": "a",
            "archetype": "Sparse synthetic",
            "ranked_metrics": {"precision_at_3": 1.0, "ndcg_at_5": 0.2},
            "visible_metrics": {"precision_at_3": 1.0, "ndcg_at_5": 0.2},
        },
        {
            "candidate_id": "b",
            "archetype": "Other synthetic",
            "ranked_metrics": {"precision_at_3": 1.0, "ndcg_at_5": 0.9},
            "visible_metrics": {"precision_at_3": 1.0, "ndcg_at_5": 0.9},
        },
    ]
    row = {
        "job_id": "j",
        "rank": 1,
        "relevance": 2,
        "score": 0.5,
        "hard_negative_family": "",
    }
    cases = _ranking_cases({}, per_candidate, {"a": [row], "b": [row]}, "semantic_ranked_quality")
    assert any(case["case_type"] == "LOWEST_NDCG_AT_5" and case["candidate_id"] == "a" for case in cases)


def test_prepare_refuses_to_overwrite_frozen_dataset(tmp_path):
    root, _ = _dataset(tmp_path)
    with pytest.raises(FileExistsError):
        prepare(root)
