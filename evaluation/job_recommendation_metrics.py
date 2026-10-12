"""Pure Task 15B candidate-query metrics; no model, DB, or production cache imports."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Iterable, Sequence


RELEVANCE_THRESHOLD = 2
PRIMARY_K = (1, 3, 5)
RECALL_K = (3, 5)
NDCG_K = (3, 5, 10)


def dcg(grades: Sequence[int], k: int) -> float:
    return math.fsum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(grades[:k], 1)
    )


def query_metrics(
    ordered_grades: Sequence[int],
    *,
    universe_grades: Sequence[int] | None = None,
) -> dict[str, float | int | None]:
    """Measure one candidate query with explicit undefined-value semantics."""
    ranked = list(ordered_grades)
    universe = list(universe_grades if universe_grades is not None else ranked)
    if any(grade not in (0, 1, 2, 3) for grade in (*ranked, *universe)):
        raise ValueError("Relevance grades must be integers from 0 through 3.")

    relevant_total = sum(grade >= RELEVANCE_THRESHOLD for grade in universe)
    first = next(
        (rank for rank, grade in enumerate(ranked, 1) if grade >= RELEVANCE_THRESHOLD),
        None,
    )
    result: dict[str, float | int | None] = {
        "first_relevant_rank": first,
        "mrr": None if relevant_total == 0 else (1.0 / first if first else 0.0),
    }
    for k in PRIMARY_K:
        result[f"precision_at_{k}"] = (
            None
            if len(ranked) < k
            else sum(grade >= RELEVANCE_THRESHOLD for grade in ranked[:k]) / k
        )
    for k in RECALL_K:
        result[f"recall_at_{k}"] = (
            None
            if relevant_total == 0 or len(ranked) < k
            else sum(grade >= RELEVANCE_THRESHOLD for grade in ranked[:k])
            / relevant_total
        )
    ideal = sorted(universe, reverse=True)
    for k in NDCG_K:
        denominator = dcg(ideal, k)
        result[f"ndcg_at_{k}"] = (
            None
            if len(ranked) < k or denominator == 0
            else dcg(ranked, k) / denominator
        )
    return result


def macro_summary(per_query: Sequence[dict[str, float | int | None]]) -> dict:
    names = [
        *(f"precision_at_{k}" for k in PRIMARY_K),
        *(f"recall_at_{k}" for k in RECALL_K),
        "mrr",
        *(f"ndcg_at_{k}" for k in NDCG_K),
    ]
    summary = {}
    for name in names:
        values = [float(row[name]) for row in per_query if row[name] is not None]
        summary[name] = {
            "mean": statistics.fmean(values) if values else None,
            "defined_queries": len(values),
            "undefined_queries": len(per_query) - len(values),
        }
    return summary


def bootstrap_macro(
    per_query: Sequence[dict[str, float | int | None]],
    *,
    resamples: int = 1000,
    seed: int = 42,
) -> dict:
    if not per_query:
        return {"unit": "candidate", "resamples": resamples, "seed": seed, "metrics": {}}
    rng = random.Random(seed)
    names = [
        *(f"precision_at_{k}" for k in PRIMARY_K),
        *(f"recall_at_{k}" for k in RECALL_K),
        "mrr",
        *(f"ndcg_at_{k}" for k in NDCG_K),
    ]
    distributions = {name: [] for name in names}
    for _ in range(resamples):
        sample = [rng.choice(per_query) for _ in per_query]
        for name in names:
            values = [float(row[name]) for row in sample if row[name] is not None]
            if values:
                distributions[name].append(statistics.fmean(values))

    def percentile(values: Sequence[float], quantile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * quantile
        lower = math.floor(position)
        upper = math.ceil(position)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    point = macro_summary(per_query)
    return {
        "unit": "candidate",
        "resamples": resamples,
        "seed": seed,
        "metrics": {
            name: {
                "point_estimate": point[name]["mean"],
                "ci_low": percentile(values, 0.025),
                "ci_high": percentile(values, 0.975),
                "defined_queries": point[name]["defined_queries"],
                "undefined_queries": point[name]["undefined_queries"],
            }
            for name, values in distributions.items()
        },
    }


def random_baseline(
    grade_pools: Iterable[Sequence[int]],
    *,
    simulations: int = 10_000,
    seed: int = 42,
) -> dict:
    pools = [list(pool) for pool in grade_pools]
    rng = random.Random(seed)
    metric_names = [
        *(f"precision_at_{k}" for k in PRIMARY_K),
        *(f"recall_at_{k}" for k in RECALL_K),
        "mrr",
        *(f"ndcg_at_{k}" for k in NDCG_K),
    ]
    totals = {name: 0.0 for name in metric_names}
    counts = {name: 0 for name in metric_names}
    for _ in range(simulations):
        rows = []
        for pool in pools:
            shuffled = pool.copy()
            rng.shuffle(shuffled)
            rows.append(query_metrics(shuffled))
        for name in metric_names:
            values = [float(row[name]) for row in rows if row[name] is not None]
            if values:
                totals[name] += statistics.fmean(values)
                counts[name] += 1
    return {
        "name": "within-candidate random-order sanity baseline",
        "simulations": simulations,
        "seed": seed,
        "macro_expectation": {
            name: totals[name] / counts[name] if counts[name] else None
            for name in metric_names
        },
    }
