"""14C.4 read-only, label-free demographic policy; safe aggregate audit only.

Never predicts attributes, regenerates scores, opens a DB or contacts a provider.
CSV sources stay immutable. Operational Category labels are copied from the
original archive, not mined from names/prose. Output contains no candidate text.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

from app.services.matching_text_privacy import find_matching_text_privacy_issues


FROZEN_INPUTS = {
    "ranking_pairs_labeled.csv": "a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d",
    "ranking_canonical_cvs.jsonl": "0a7da44fde0cde5f0ff45259093bb7f194cbc40bea502bf02c50bfe66682f615",
    "ranking_canonical_jds.jsonl": "9da55f0731adf98c1c7aefe7072759effc04816f6568ddee9caef9f1e14fedc1",
    "ranking_canonical_pair_manifest.csv": "cd715793e5ba37272d7cd1b82847f58e78879b1aaaf2577efab1c520f1ae92b9",
}
SOURCE_SHA = "816a7cd985a9a41e3ce8d1e83cb7e1beb1e854a89c1cf1fd0d75494faaa0559d"
JOB_SOURCE_SHA = "d782e95f35cbd5f658ad7124021c938f5c8c1656f1c059b6dc9d402d1eaa195f"
# These are TEXT CUES, never person/group labels or proof of a protected identity.
TEXT_CUES = {
    "gendered_pronoun_terms": re.compile(r"\b(?:he|she|him|her|his|hers)\b", re.I),
    "sensitive_topic_terms": re.compile(r"\b(?:gender|female|male|religion|disabled|disability|marital|citizenship|nationality|ethnicity|sexual orientation|political affiliation)\b", re.I),
    "four_digit_year_cues": re.compile(r"\b(?:19|20)\d{2}\b"),
    "address_label": re.compile(r"\b(?:home address|address|địa chỉ)\s*:", re.I),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def csv_rows(path):
    csv.field_size_limit(20_000_000)
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), reader.fieldnames


def cohort_metrics(predictions, categories):
    """Per-candidate/per-job exposure, NOT calibrated cross-job score means.

    Retain tiny/missing groups and explicit denominators; no significance claim.
    Offline score coverage is not production RANKED availability.
    """
    jobs = defaultdict(list)
    pairs = set()
    for row in predictions:
        if row["pair_id"] in pairs:
            raise ValueError("Duplicate prediction pair")
        pairs.add(row["pair_id"])
        if row["cv_id"] not in categories:
            raise ValueError("Missing source category identity")
        if not math.isfinite(float(row["semantic_score"])):
            raise ValueError("Invalid frozen score")
        jobs[row["job_id"]].append(row)
    for pool in jobs.values():
        if sorted(int(r["rank"]) for r in pool) != list(range(1, len(pool)+1)):
            raise ValueError("Incomplete or duplicate full-list ranks")
    groups = defaultdict(list)
    for row in predictions:
        groups[categories[row["cv_id"]] or "MISSING_SOURCE_CATEGORY"].append(row)
    result = []
    for category, rows in sorted(groups.items()):
        n = len(rows)
        result.append({
            "cohort_type": "source_occupation_category", "cohort_value": category,
            "protected": False, "n_candidate_job_rows": n,
            "unique_cvs": len({r["cv_id"] for r in rows}),
            "jobs_represented": len({r["job_id"] for r in rows}),
            "grade_counts": {grade: sum(r["relevance_grade"] == grade for r in rows) for grade in ("0","1","2")},
            "mean_within_job_rank": statistics.mean(int(r["rank"]) for r in rows),
            "mean_within_job_rank_fraction": statistics.mean(
                (int(r["rank"])-1)/(len(jobs[r["job_id"]])-1)
                if len(jobs[r["job_id"]]) > 1 else 0. for r in rows),
            "top1_count": sum(int(r["rank"]) <= 1 for r in rows),
            "top3_count": sum(int(r["rank"]) <= 3 for r in rows),
            "top5_count": sum(int(r["rank"]) <= 5 for r in rows),
            "top1_rate": sum(int(r["rank"]) <= 1 for r in rows)/n,
            "top3_rate": sum(int(r["rank"]) <= 3 for r in rows)/n,
            "top5_rate": sum(int(r["rank"]) <= 5 for r in rows)/n,
            "offline_scored_count": n,
            "production_ranked_rate": None, "production_pending_rate": None,
            "production_unavailable_rate": None, "production_error_rate": None,
            "size_guard": "DESCRIPTIVE_ONLY_N_LT_5" if n < 5 else
                          "HIGH_UNCERTAINTY_N_LT_10" if n < 10 else "DESCRIPTIVE_NOT_CAUSAL",
        })
    return result


def text_inventory(records, kind):
    counts = Counter({"supported_contact_issue_"+key: 0 for key in ("email", "phone", "contact_url")})
    for record in records:
        canonical = record["canonical_input"]
        text = canonical["semantic_text"]
        if record["status"] != "SUCCEEDED" or not isinstance(text, str):
            raise ValueError("Invalid canonical record")
        for issue in find_matching_text_privacy_issues(text):
            counts["supported_contact_issue_"+issue] += 1
        for name, pattern in TEXT_CUES.items():
            counts[name] += bool(pattern.search(text))
        counts["location_metadata_present"] += canonical.get("location") is not None
        if kind == "cv":
            for name in ["career_objective", "skills", "experiences", "educations", "projects", "certificates", "languages"]:
                counts["canonical_field_present_"+name] += bool(canonical.get(name))
            normalized = " ".join(text.casefold().split())
            # Literal overlap is indirect prose evidence, not proof that the
            # mapper intentionally concatenates these structured metadata fields.
            for section, field in [("experiences","company_name"), ("educations","school_name")]:
                counts["literal_"+field+"_overlap"] += any(
                    " ".join(str(item.get(field) or "").casefold().split()) in normalized
                    for item in canonical[section] if item.get(field))
    return {"entities": len(records), "document_cue_counts_not_group_labels": dict(sorted(counts.items())),
            "coverage_note": "Finite literal cues/contact patterns only; not NER or comprehensive sensitive-content certification."}


def audit(root, source, job_source=None):
    derived = root / "evaluation/data/derived"
    frozen = {name: sha(derived/name) for name in FROZEN_INPUTS}
    if frozen != FROZEN_INPUTS or sha(source) != SOURCE_SHA:
        raise ValueError("Frozen/source hash mismatch")
    truth, columns = csv_rows(derived/"ranking_pairs_labeled.csv")
    predictions, prediction_columns = csv_rows(root/"evaluation/results/ranking-semantic-v1/predictions.csv")
    truth_by_pair = {r["pair_id"]: r for r in truth}
    if len(truth) != 100 or len(truth_by_pair) != 100 or len(predictions) != 100:
        raise ValueError("Invalid fixed pair coverage")
    for row in predictions:
        original = truth_by_pair.get(row["pair_id"])
        if original is None or any(row[k] != original[k] for k in ["cv_id","job_id","ranking_case_id","relevance_grade"]):
            raise ValueError("Prediction identity/label mismatch")
    cv_records = [json.loads(line) for line in (derived/"ranking_canonical_cvs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    jd_records = [json.loads(line) for line in (derived/"ranking_canonical_jds.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    refs = {r["cv_id"]: r["source_ref"] for r in cv_records}
    if len(refs) != 95 or len(jd_records) != 10:
        raise ValueError("Invalid entity coverage")
    source_rows, source_columns = csv_rows(source)
    categories = {}
    for reference, row in enumerate(source_rows, 2):
        cid = row["ID"].strip()
        if cid in refs:
            if cid in categories or str(reference) != str(refs[cid]):
                raise ValueError("Source identity/reference mismatch")
            categories[cid] = row["Category"].strip()
    if set(categories) != set(refs):
        raise ValueError("Missing selected source metadata")
    # No raw corpus data or original category row/identity leaves this scope.
    result = {
        "task": "14C.4", "audit_policy": "STATIC_AND_FROZEN_SCORE_DESCRIPTIVE_ONLY",
        "frozen_input_sha256": frozen,
        "source_metadata_sha256": SOURCE_SHA,
        "prediction_sha256": sha(root/"evaluation/results/ranking-semantic-v1/predictions.csv"),
        "protected_group_labels_available": False,
        "protected_group_disparity_measured": False,
        "protected_group_boundary": "No reliable governed protected-group labels in inspected benchmark metadata; never infer from prose, names, dates or photos.",
        "group_inventory": [
            {"field": "Category", "source": "Resume.csv", "protected": False, "usable": True,
             "sample_count": len(categories), "purpose": "Descriptive occupation cohort exposure in existing ranks"},
            {"field": "source_type", "source": "canonical CV envelope", "protected": False,
             "usable": "SINGLE_OFFLINE_ORIGIN_NOT_BUILDER_UPLOADED", "sample_count": 95,
             "values": dict(Counter(r["source_type"] for r in cv_records)), "purpose": "Coverage only, not production source-type parity"},
            {"field": "document MIME type / production availability", "source": "Production schemas, not this corpus",
             "protected": False, "usable": False, "sample_count": 0, "purpose": "Requires appropriately scoped operational telemetry; no DEV DB sampling"},
            {"field": "protected demographic labels", "source": "Inspected benchmark/source metadata",
             "protected": True, "usable": False, "sample_count": 0, "purpose": "No inference/fabrication"},
        ],
        "dataset_columns": columns, "prediction_columns": prediction_columns,
        "source_columns": source_columns,
        "cv_text_inventory": text_inventory(cv_records,"cv"),
        "jd_text_inventory": text_inventory(jd_records,"jd"),
        "operational_cohort_metrics": cohort_metrics(predictions,categories),
        "production_availability_measured": False,
        "production_pending_duration_measured": False,
        "model_calls": 0, "db_access": False,
        "notes": ["100 candidate-job rows/95 unique CVs/10 jobs, five reused CVs; no independent-observation assumption",
                  "No cross-job score mean, causal disparity test, p-value or demographic label",
                  "TopK is audit only, not new production limit", "Missing production rates remain null, not zero"],
    }
    if job_source is not None:
        if sha(job_source) != JOB_SOURCE_SHA:
            raise ValueError("Job source hash mismatch")
        job_rows, job_columns = csv_rows(job_source)
        job_refs = {r["job_id"]: r["source_ref"] for r in jd_records}
        selected = {}
        for reference,row in enumerate(job_rows,2):
            jid=row["job_id"].strip()
            if jid in job_refs:
                if jid in selected or str(reference) != str(job_refs[jid]):
                    raise ValueError("Job source reference mismatch")
                selected[jid]=row
        if set(selected) != set(job_refs):
            raise ValueError("Missing selected job metadata")
        result["job_source_sha256"] = JOB_SOURCE_SHA
        result["job_source_columns"] = job_columns
        result["group_inventory"].extend([
            {"field":field,"source":"job_postings.csv","protected":False,
             "usable":"JOB_METADATA_ONLY_NOT_CANDIDATE_ATTRIBUTE",
             "sample_count":sum(bool(row.get(field,"").strip()) for row in selected.values()),
             "purpose":"Availability inventory only; do not infer candidate region/experience/protected group"}
            for field in ("formatted_experience_level","location","formatted_work_type")
        ])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--job-source", type=Path)
    args = parser.parse_args()
    # Print safe aggregate JSON; caller persists reviewed summary via apply_patch.
    print(json.dumps(audit(Path(__file__).resolve().parents[1], args.source, args.job_source), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
