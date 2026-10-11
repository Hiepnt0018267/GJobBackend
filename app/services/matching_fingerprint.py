"""Deterministic fingerprints of the exact signals consumed by matching engines."""

import hashlib
import json
from collections.abc import Mapping, Sequence

from app.schemas.matching import CanonicalCVMatchingInput, CanonicalJobMatchingInput
from app.services.matching_text_privacy import MATCHING_CANONICAL_VERSION


def _sha256_json(payload: Mapping[str, str | Sequence[str]]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def fingerprint_cv(cv: CanonicalCVMatchingInput) -> str:
    return _sha256_json(
        {
            "canonical_version": MATCHING_CANONICAL_VERSION,
            "semantic_text": cv.semantic_text,
            "skills": sorted(skill.normalized_name for skill in cv.skills),
            "project_technologies": sorted(
                technology.normalized_name
                for project in cv.projects
                for technology in project.technologies
            ),
        }
    )


def fingerprint_job(job: CanonicalJobMatchingInput) -> str:
    return _sha256_json(
        {
            "canonical_version": MATCHING_CANONICAL_VERSION,
            "semantic_text": job.semantic_text,
            "skills": sorted(skill.normalized_name for skill in job.skills),
        }
    )
