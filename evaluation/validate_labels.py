from __future__ import annotations

import argparse
import csv
from pathlib import Path

from evaluation.common import (
    EvaluationDataError, PAIR_ID_PATTERN, PAIR_TYPES, REQUIRED_COLUMNS, iter_csv,
    make_pair_id, normalize_identifier, normalize_whitespace, resolve_dataset_files, write_csv,
)


REQUIRED_DRAFT_FIELDS = {
    "pair_id", "cv_id", "job_id", "pair_type", "cv_category", "job_title",
    "sampling_score", "cv_text_preview", "job_text_preview", "cv_source_row",
    "job_source_row", "label", "label_reason",
}
FINAL_FIELDS = [
    "pair_id", "cv_id", "job_id", "label", "pair_type", "cv_category",
    "job_title", "label_reason", "sampling_score", "job_industry",
    "cv_skills_hint", "job_skills_hint", "review_notes",
]


def _source_ids(data_dir: str | Path) -> tuple[set[str], set[str]]:
    files = resolve_dataset_files(data_dir)
    cv_ids = {
        normalize_identifier(row["ID"])
        for _, row in iter_csv(files["Resume.csv"], required_columns=REQUIRED_COLUMNS["Resume.csv"])
        if normalize_identifier(row["ID"]) and normalize_whitespace(row["Resume_str"])
    }
    job_ids = {
        normalize_identifier(row["job_id"])
        for _, row in iter_csv(files["job_postings.csv"], required_columns=REQUIRED_COLUMNS["job_postings.csv"])
        if normalize_identifier(row["job_id"]) and normalize_whitespace(row["title"]) and normalize_whitespace(row["description"])
    }
    return cv_ids, job_ids


def validate_labeled_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    data_dir: str | Path | None = None,
) -> dict[str, int]:
    source = Path(input_path)
    if not source.is_file():
        raise EvaluationDataError(f"Labeled CSV does not exist: {source}")
    known_cv_ids: set[str] | None = None
    known_job_ids: set[str] | None = None
    if data_dir is not None:
        known_cv_ids, known_job_ids = _source_ids(data_dir)

    errors: list[str] = []
    valid_rows: list[dict[str, str]] = []
    seen_pair_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    with source.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = REQUIRED_DRAFT_FIELDS - set(reader.fieldnames or ())
        if missing_columns:
            raise EvaluationDataError(
                f"Labeled CSV is missing column(s): {', '.join(sorted(missing_columns))}"
            )
        for line_number, row in enumerate(reader, start=2):
            pair_id = normalize_whitespace(row.get("pair_id"))
            cv_id = normalize_identifier(row.get("cv_id"))
            job_id = normalize_identifier(row.get("job_id"))
            pair_type = normalize_whitespace(row.get("pair_type"))
            label = normalize_whitespace(row.get("label"))
            reason = normalize_whitespace(row.get("label_reason"))
            prefix = f"line {line_number}"
            if not PAIR_ID_PATTERN.fullmatch(pair_id) or (cv_id and job_id and pair_id != make_pair_id(cv_id, job_id)):
                errors.append(f"{prefix}: invalid pair_id")
            if not cv_id or not normalize_whitespace(row.get("cv_source_row")):
                errors.append(f"{prefix}: missing CV reference")
            if not job_id or not normalize_whitespace(row.get("job_source_row")):
                errors.append(f"{prefix}: missing JD reference")
            if known_cv_ids is not None and cv_id not in known_cv_ids:
                errors.append(f"{prefix}: CV ID not present in source dataset")
            if known_job_ids is not None and job_id not in known_job_ids:
                errors.append(f"{prefix}: job ID not present in source dataset")
            if pair_type not in PAIR_TYPES:
                errors.append(f"{prefix}: invalid pair_type")
            if label not in {"0", "1"}:
                errors.append(f"{prefix}: label must be 0 or 1")
            if not reason:
                errors.append(f"{prefix}: label_reason is required")
            if not normalize_whitespace(row.get("cv_text_preview")) and (known_cv_ids is None or cv_id not in known_cv_ids):
                errors.append(f"{prefix}: empty CV review text")
            if not normalize_whitespace(row.get("job_text_preview")) and (known_job_ids is None or job_id not in known_job_ids):
                errors.append(f"{prefix}: empty JD review text")
            pair = (cv_id, job_id)
            if pair_id in seen_pair_ids or pair in seen_pairs:
                errors.append(f"{prefix}: duplicate CV/JD pair")
            seen_pair_ids.add(pair_id)
            seen_pairs.add(pair)
            valid_rows.append({field: normalize_whitespace(row.get(field)) for field in FINAL_FIELDS})

    if errors:
        preview = "\n".join(f"- {error}" for error in errors[:25])
        remainder = f"\n- ... and {len(errors) - 25} more" if len(errors) > 25 else ""
        raise EvaluationDataError(f"Label validation failed with {len(errors)} error(s):\n{preview}{remainder}")
    if not valid_rows:
        raise EvaluationDataError("Labeled CSV contains no data rows.")
    write_csv(Path(output_path), valid_rows, FINAL_FIELDS)
    label_counts = {"0": 0, "1": 0}
    for row in valid_rows:
        label_counts[row["label"]] += 1
    return {"rows": len(valid_rows), "label_0": label_counts["0"], "label_1": label_counts["1"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate human labels and emit a benchmark-ready final CSV.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="evaluation/data/derived/evaluation_pairs_final.csv")
    parser.add_argument("--data-dir", help="Optional raw dataset directory for strict source-ID validation.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = validate_labeled_file(args.input, args.output, data_dir=args.data_dir)
    except EvaluationDataError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Labels valid: {summary['rows']} rows ({summary['label_1']} relevant, {summary['label_0']} not relevant)")
    print(f"Final dataset: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
