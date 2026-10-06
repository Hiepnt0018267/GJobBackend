from __future__ import annotations

import csv
import hashlib
import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path


EXPECTED_FILES = (
    "Resume.csv",
    "job_postings.csv",
    "job_skills.csv",
    "job_industries.csv",
    "companies.csv",
    "company_industries.csv",
    "company_specialities.csv",
    "benefits.csv",
    "employee_counts.csv",
)

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "Resume.csv": {"ID", "Resume_str", "Resume_html", "Category"},
    "job_postings.csv": {"job_id", "company_id", "title", "description"},
    "job_skills.csv": {"job_id", "skill_abr"},
    "job_industries.csv": {"job_id", "industry_id"},
    "companies.csv": {"company_id", "name"},
    "company_industries.csv": {"company_id", "industry"},
    "company_specialities.csv": {"company_id", "speciality"},
    "benefits.csv": {"job_id", "type"},
    "employee_counts.csv": {"company_id", "employee_count"},
}

PAIR_TYPES = (
    "POSITIVE_CANDIDATE",
    "HARD_NEGATIVE_CANDIDATE",
    "EASY_NEGATIVE_CANDIDATE",
)
PAIR_ID_PATTERN = re.compile(r"^pair_[0-9a-f]{20}$")


class EvaluationDataError(ValueError):
    """Raised when an evaluation input or artifact is invalid."""


@dataclass(frozen=True)
class EvaluationConfig:
    seed: int = 42
    minimum_cv_chars: int = 200
    minimum_job_description_chars: int = 100
    cv_sample_size: int = 120
    job_sample_size: int = 140
    pair_target: int = 400
    max_pairs_per_cv: int = 4
    max_pairs_per_job: int = 4
    cv_preview_chars: int = 2400
    job_preview_chars: int = 2400
    candidate_pool_limit: int = 60


def normalize_whitespace(value: str | None) -> str:
    return " ".join((value or "").split())


def normalize_key(value: str | None) -> str:
    return normalize_whitespace(value).casefold()


def normalize_identifier(value: str | None) -> str:
    """Normalize CSV integer IDs without changing opaque/alphanumeric identifiers."""
    normalized = normalize_whitespace(value)
    if re.fullmatch(r"[+-]?\d+\.0+", normalized):
        return normalized.split(".", 1)[0]
    return normalized


_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+#.\-]{1,}")
_STOPWORDS = {
    "and", "are", "for", "from", "have", "job", "our", "the", "this",
    "to", "with", "will", "you", "your", "years", "year", "work", "team",
    "skills", "experience", "required", "preferred", "responsibilities",
    "ability", "including", "using", "within", "role", "position", "company",
}


def tokenize(value: str | None) -> frozenset[str]:
    return frozenset(
        token
        for token in _TOKEN_PATTERN.findall(normalize_key(value))
        if token not in _STOPWORDS and len(token) >= 3
    )


def stable_rank(seed: int, *parts: str) -> str:
    raw = "|".join((str(seed), *parts)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def exact_text_hash(value: str | None) -> str | None:
    normalized = normalize_key(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None


def near_duplicate_hash(value: str | None) -> str | None:
    normalized = re.sub(r"\d+", "#", normalize_key(value))
    normalized = normalize_whitespace(re.sub(r"[^a-z#]+", " ", normalized))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None


def make_pair_id(cv_id: str, job_id: str) -> str:
    digest = hashlib.sha256(f"{cv_id}|{job_id}".encode("utf-8")).hexdigest()[:20]
    return f"pair_{digest}"


def percentile(values: list[int], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def length_statistics(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {"min": None, "median": None, "p90": None, "p95": None, "max": None}
    return {
        "min": min(values),
        "median": percentile(values, 0.5),
        "p90": percentile(values, 0.9),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }


def resolve_dataset_files(data_dir: str | Path) -> dict[str, Path]:
    root = Path(data_dir).expanduser().resolve()
    if not root.is_dir():
        raise EvaluationDataError(f"Dataset directory does not exist: {root}")
    expected_lower = {name.casefold(): name for name in EXPECTED_FILES}
    by_name: dict[str, list[Path]] = {}
    for path in root.rglob("*.csv"):
        canonical = expected_lower.get(path.name.casefold())
        if canonical:
            by_name.setdefault(canonical, []).append(path)
    missing = [name for name in EXPECTED_FILES if name not in by_name]
    if missing:
        raise EvaluationDataError(
            f"Missing required dataset file(s) under {root}: {', '.join(missing)}"
        )
    resolved: dict[str, Path] = {}
    for name, matches in by_name.items():
        if len(matches) > 1:
            locations = ", ".join(str(item) for item in sorted(matches))
            raise EvaluationDataError(f"Multiple {name} files found: {locations}")
        resolved[name] = matches[0]
    return resolved


def iter_csv(path: Path, *, required_columns: Iterable[str] = ()) -> Iterator[tuple[int, dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing = set(required_columns) - fieldnames
        if missing:
            raise EvaluationDataError(
                f"{path.name} is missing required column(s): {', '.join(sorted(missing))}"
            )
        for source_row, row in enumerate(reader, start=2):
            yield source_row, {key: value or "" for key, value in row.items() if key is not None}


def inspect_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration as exc:
            raise EvaluationDataError(f"Dataset file is empty: {path}") from exc


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
