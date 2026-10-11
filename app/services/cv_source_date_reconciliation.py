"""Deterministic source-grounded chronology reconciliation for provider CV data.

This layer runs only after provider-wire validation and before canonical validation.
It never calls a model, guesses a date, swaps values by position, drops records, or
changes non-date fields.
"""

from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.schemas.partial_date import OpenEndedDate, PartialDate, definitely_reversed
from app.schemas.source_date_consistency import (
    CONSISTENCY_VERSION,
    SourceDateConsistency,
    VerifiedSourceConflicts,
    conflict_binding,
)
from app.services.cv_date_evidence import _ADAPTER, _CURRENT, _DATE, _RANGE, _normalized
from app.services.cv_experience_alignment import align_experiences_to_source, phrase_pattern


RESOLVER_VERSION = "cv-source-grounded-date-reconciliation-v1"

RESOLVED_EXPLICIT_RANGE = "RESOLVED_EXPLICIT_RANGE"
RESOLVED_OPEN_ENDED_RANGE = "RESOLVED_OPEN_ENDED_RANGE"
RESOLVED_CERTIFICATE_ISSUE_DATE = "RESOLVED_CERTIFICATE_ISSUE_DATE"
RESOLVED_CERTIFICATE_EXPIRATION = "RESOLVED_CERTIFICATE_EXPIRATION"
SOURCE_DATE_AMBIGUOUS = "SOURCE_DATE_AMBIGUOUS"
SOURCE_DATE_UNMATCHED = "SOURCE_DATE_UNMATCHED"
SOURCE_DATA_CONFLICT = "SOURCE_DATA_CONFLICT"
UNSUPPORTED_DATE_PATTERN = "UNSUPPORTED_DATE_PATTERN"

UNVERIFIED_OPTIONAL_DATE_OMITTED = "UNVERIFIED_OPTIONAL_DATE_OMITTED"
AMBIGUOUS_OPTIONAL_DATE_OMITTED = "AMBIGUOUS_OPTIONAL_DATE_OMITTED"
SOURCE_DATE_UNMATCHED_OMITTED = "SOURCE_DATE_UNMATCHED_OMITTED"
SOURCE_DATE_AMBIGUOUS_OMITTED = "SOURCE_DATE_AMBIGUOUS_OMITTED"

NO_NAME_ANCHOR = "NO_NAME_ANCHOR"
NO_ISSUER_ANCHOR = "NO_ISSUER_ANCHOR"
NO_LOCAL_DATE_EVIDENCE = "NO_LOCAL_DATE_EVIDENCE"
DATE_OUTSIDE_RECORD_BOUNDARY = "DATE_OUTSIDE_RECORD_BOUNDARY"
IDENTITY_NOT_UNIQUE = "IDENTITY_NOT_UNIQUE"
MULTIPLE_LOCAL_DATE_MAPPINGS = "MULTIPLE_LOCAL_DATE_MAPPINGS"
UNSUPPORTED_LAYOUT = "UNSUPPORTED_LAYOUT"

_ISSUE = re.compile(
    r"(?:issued?|awarded|obtained|ngày\s+cấp|cấp\s+ngày)\s*[:\-]?\s*(?P<date>" + _DATE + r"|" + _CURRENT + r")",
    re.I,
)
_EXPIRATION = re.compile(
    r"(?:expires?|expiration|expiry|valid\s+until|hết\s+hạn|có\s+hiệu\s+lực\s+đến)"
    r"\s*[:\-]?\s*(?P<date>" + _DATE + r"|" + _CURRENT + r")",
    re.I,
)
_ANY_DATE = re.compile(r"(?<!\w)(?P<date>" + _DATE + r")(?!\w)", re.I)


class SourceDateResolutionError(ValueError):
    """Safe typed failure; never contains source text or provider values."""

    def __init__(
        self,
        code: str,
        entity_type: str,
        entity_index: int,
        *,
        detail_code: str | None = None,
        diagnostics: dict[str, int] | None = None,
    ):
        super().__init__(f"{code}:{entity_type}[{entity_index}]")
        self.code = code
        self.entity_type = entity_type
        self.entity_index = entity_index
        self.detail_code = detail_code
        self.diagnostics = dict(diagnostics or {})


@dataclass(frozen=True)
class SourceDateResolution:
    payload: dict[str, Any]
    validation_context: dict[str, Any]
    audit: tuple[dict[str, Any], ...]
    diagnostics: dict[str, int] = field(default_factory=dict)


def _serialized(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value.isoformat()


def _parsed(value):
    return _ADAPTER.validate_python(value) if value is not None else None


def _invalid_pair(start, end) -> bool:
    try:
        return definitely_reversed(_parsed(start), _parsed(end))
    except ValueError:
        return True


def _safe_audit(
    entity_type, index, status, fields, span, source_text,
    *, matcher=None, reason=None, detail_reason=None,
):
    start, end = span
    normalized = _normalized(source_text)
    source_slice = normalized[max(0, start):max(0, end)]
    result = {
        "entity_type": entity_type,
        "entity_index": index,
        "status": status,
        "affected_fields": list(fields),
        "source_span": [start, end],
        "source_span_sha256": hashlib.sha256(source_slice.encode()).hexdigest(),
        "resolver_version": RESOLVER_VERSION,
    }
    if reason:
        result["reason"] = reason
    if detail_reason:
        result["detail_reason"] = detail_reason
    if matcher:
        result["matcher"] = dict(matcher)
    return result


def _experience_resolution(source_text, payload, proofs, audit):
    experiences = payload.get("experiences", [])
    invalid_indices = []
    for index, item in enumerate(experiences):
        if not isinstance(item, dict):
            continue
        metadata_value = item.get("date_consistency")
        if metadata_value is not None:
            metadata = SourceDateConsistency.model_validate(metadata_value)
            proofs.add(conflict_binding(item, metadata))
            continue
        if _invalid_pair(item.get("start_date"), item.get("end_date")):
            invalid_indices.append(index)
    if not invalid_indices:
        return

    subset = [experiences[index] for index in invalid_indices]
    try:
        alignments = align_experiences_to_source(subset, source_text)
    except ValueError as exc:
        code = SOURCE_DATE_AMBIGUOUS if "AMBIGUOUS" in str(exc) else SOURCE_DATE_UNMATCHED
        raise SourceDateResolutionError(code, "experiences", invalid_indices[0]) from exc

    for alignment in alignments:
        index = invalid_indices[alignment["experience_index"]]
        item = experiences[index]
        start, end = alignment["dates"]
        if definitely_reversed(start, end):
            if alignment["status"] != "unique_ordered_assignment":
                raise SourceDateResolutionError(SOURCE_DATE_AMBIGUOUS, "experiences", index)
            item["start_date"] = _serialized(start)
            item["end_date"] = _serialized(end)
            item["is_current"] = isinstance(end, OpenEndedDate)
            source_hash = hashlib.sha256(source_text.encode()).hexdigest()
            metadata = SourceDateConsistency(
                state="SOURCE_DATA_CONFLICT",
                source_sha256=source_hash,
                normalized_range_offsets=tuple(alignment["range_offsets"]),
            )
            item["date_consistency"] = metadata.model_dump(mode="json")
            proofs.add(conflict_binding(item, metadata))
            audit.append(_safe_audit(
                "experiences", index, SOURCE_DATA_CONFLICT,
                ("start_date", "end_date", "date_consistency"),
                alignment["range_offsets"], source_text,
            ))
            continue
        item["start_date"] = _serialized(start)
        item["end_date"] = _serialized(end)
        item["is_current"] = isinstance(end, OpenEndedDate)
        audit.append(_safe_audit(
            "experiences", index,
            RESOLVED_OPEN_ENDED_RANGE if isinstance(end, OpenEndedDate) else RESOLVED_EXPLICIT_RANGE,
            ("start_date", "end_date", "is_current"),
            alignment["range_offsets"], source_text,
        ))


def _unique_date(matches, group="date"):
    values = {}
    for match in matches:
        token = match[group]
        parsed = OpenEndedDate(state="current") if re.fullmatch(_CURRENT, token, re.I) else _parsed(token)
        key = parsed.model_dump_json() if hasattr(parsed, "model_dump_json") else parsed.isoformat()
        values[key] = parsed
    if len(values) > 1:
        return None, True
    return (next(iter(values.values())) if values else None), False


def _certificate_evidence(segment, diagnostics=None):
    ranges = list(_RANGE.finditer(segment))
    signatures = {}
    for match in ranges:
        start = _parsed(match["start"])
        end = OpenEndedDate(state="current") if re.fullmatch(_CURRENT, match["end"], re.I) else _parsed(match["end"])
        signature = (_serialized(start), str(_serialized(end)))
        signatures[str(signature)] = (start, end, match.span(),
            RESOLVED_OPEN_ENDED_RANGE if isinstance(end, OpenEndedDate) else RESOLVED_EXPLICIT_RANGE)
    if len(signatures) > 1:
        return None, SOURCE_DATE_AMBIGUOUS
    if signatures:
        return next(iter(signatures.values())), None

    issue_matches = list(_ISSUE.finditer(segment))
    expiration_matches = list(_EXPIRATION.finditer(segment))
    issue, issue_ambiguous = _unique_date(issue_matches)
    expiration, expiration_ambiguous = _unique_date(expiration_matches)
    if diagnostics is not None:
        if issue_ambiguous:
            diagnostics["ambiguous_candidate_count"] += 1
            diagnostics["issue_ambiguous"] = 1
        if expiration_ambiguous:
            diagnostics["ambiguous_candidate_count"] += 1
            diagnostics["expiration_ambiguous"] = 1

    if issue_ambiguous and expiration_ambiguous:
        return None, SOURCE_DATE_AMBIGUOUS
    if isinstance(issue, OpenEndedDate):
        return None, UNSUPPORTED_DATE_PATTERN

    if issue is not None and expiration_ambiguous:
        start = min((match.start() for match in issue_matches), default=0)
        end = max((match.end() for match in issue_matches), default=len(segment))
        return (issue, None, (start, end), RESOLVED_CERTIFICATE_ISSUE_DATE), None

    if expiration is not None and issue_ambiguous:
        start = min((match.start() for match in expiration_matches), default=0)
        end = max((match.end() for match in expiration_matches), default=len(segment))
        return (None, expiration, (start, end), RESOLVED_CERTIFICATE_EXPIRATION), None

    if issue_ambiguous or expiration_ambiguous:
        return None, SOURCE_DATE_AMBIGUOUS

    if issue is not None:
        start = min((match.start() for match in issue_matches + expiration_matches), default=0)
        end = max((match.end() for match in issue_matches + expiration_matches), default=len(segment))
        status = RESOLVED_CERTIFICATE_EXPIRATION if expiration is not None else RESOLVED_CERTIFICATE_ISSUE_DATE
        return (issue, expiration, (start, end), status), None
    if expiration is not None:
        start = min((match.start() for match in expiration_matches), default=0)
        end = max((match.end() for match in expiration_matches), default=len(segment))
        return (None, expiration, (start, end), RESOLVED_CERTIFICATE_EXPIRATION), None

    dates = list(_ANY_DATE.finditer(segment))
    value, ambiguous = _unique_date(dates)
    if ambiguous:
        return None, SOURCE_DATE_AMBIGUOUS
    if value is not None and not isinstance(value, OpenEndedDate):
        match = dates[0]
        return (value, None, match.span(), RESOLVED_CERTIFICATE_ISSUE_DATE), None
    if re.search(r"(?<!\w)" + _CURRENT + r"(?!\w)", segment, re.I):
        return None, UNSUPPORTED_DATE_PATTERN
    return None, SOURCE_DATE_UNMATCHED


_CERTIFICATE_BULLET = re.compile(r"[\u2022\u2023\u25aa\u25ab\u25cf\u25e6\u25a0\u25c6]+")
_CERTIFICATE_DASHES = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-",
                                     "\u2013": "-", "\u2014": "-", "\u2212": "-"})


def _certificate_source_text(source_text):
    """Normalize superficial layout while preserving line/bullet record units."""

    text = unicodedata.normalize("NFKC", source_text).translate(_CERTIFICATE_DASHES)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CERTIFICATE_BULLET.sub("\n", text)
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).casefold()


def _line_spans(text):
    return [(match.start(), match.end(), match.group()) for match in re.finditer(r"[^\n]+", text)]


def _line_index(lines, position):
    for index, (start, end, _) in enumerate(lines):
        if start <= position < end:
            return index
    return max(0, len(lines) - 1)


def _date_matches(text):
    matches = list(_ANY_DATE.finditer(text))
    matches.extend(re.finditer(r"(?<!\w)" + _CURRENT + r"(?!\w)", text, re.I))
    return sorted(matches, key=lambda match: match.span())


def _certificate_match_diagnostics():
    return {
        "name_anchor_count": 0,
        "issuer_anchor_count": 0,
        "candidate_span_count": 0,
        "date_before_name_count": 0,
        "date_inline_count": 0,
        "date_after_name_count": 0,
        "candidate_date_count": 0,
        "ambiguous_candidate_count": 0,
        "boundary_rejection_count": 0,
    }


def _raise_certificate(code, index, detail_code, diagnostics):
    raise SourceDateResolutionError(
        code,
        "certificates",
        index,
        detail_code=detail_code,
        diagnostics=diagnostics,
    )


def _all_certificate_anchors(certificates, text):
    anchors = set()
    for record in certificates:
        if not isinstance(record, dict):
            continue
        for hit in re.finditer(phrase_pattern(record.get("name") or ""), text, re.I):
            anchors.add((hit.start(), hit.end()))
    return sorted(anchors)


def _adjacent_identity_hits(pattern, text, lines, name_hit, previous_anchor, next_anchor):
    if not pattern or pattern == r"(?!)":
        return []
    name_first_line = _line_index(lines, name_hit.start())
    name_last_line = _line_index(lines, max(name_hit.start(), name_hit.end() - 1))
    previous_line = _line_index(lines, previous_anchor[0]) if previous_anchor is not None else None
    next_line = _line_index(lines, next_anchor[0]) if next_anchor is not None else None
    result = []
    for hit in re.finditer(pattern, text, re.I):
        if previous_anchor is not None and hit.start() < previous_anchor[1]:
            continue
        if next_anchor is not None and hit.end() > next_anchor[0]:
            continue
        hit_first_line = _line_index(lines, hit.start())
        hit_last_line = _line_index(lines, max(hit.start(), hit.end() - 1))
        if previous_line is not None and hit_first_line <= previous_line <= hit_last_line:
            continue
        if next_line is not None and hit_first_line <= next_line <= hit_last_line:
            continue
        if hit_first_line <= name_last_line + 1 and hit_last_line >= name_first_line - 1:
            result.append(hit)
    return result


def _certificate_record_span(text, lines, name_hit, issuer_hit, previous_anchor, next_anchor, diagnostics):
    name_first_line = _line_index(lines, name_hit.start())
    name_last_line = _line_index(lines, max(name_hit.start(), name_hit.end() - 1))
    first_line = name_first_line
    last_line = name_last_line
    if issuer_hit is not None:
        first_line = min(first_line, _line_index(lines, issuer_hit.start()))
        last_line = max(last_line, _line_index(lines, max(issuer_hit.start(), issuer_hit.end() - 1)))
    identity_first_line = first_line
    identity_last_line = last_line

    previous_line = _line_index(lines, previous_anchor[0]) if previous_anchor is not None else None
    next_line = _line_index(lines, next_anchor[0]) if next_anchor is not None else None

    # A leading date is safe only before the first certificate anchor, or when the
    # current issuer itself occupies that leading unit.  This prevents certificate B
    # from stealing certificate A's trailing date.
    cursor = identity_first_line - 1
    while cursor >= 0 and identity_first_line - cursor <= 2:
        line_text = lines[cursor][2]
        issuer_in_line = issuer_hit is not None and lines[cursor][0] <= issuer_hit.start() < lines[cursor][1]
        if previous_line is not None and not issuer_in_line:
            if _date_matches(line_text):
                diagnostics["boundary_rejection_count"] += 1
            break
        if not _date_matches(line_text) and not issuer_in_line:
            break
        first_line = cursor
        cursor -= 1

    # Trailing date/issuer lines belong to this record only until the next known
    # certificate anchor.  At most two adjacent logical units are admitted.
    cursor = identity_last_line + 1
    while cursor < len(lines) and cursor - identity_last_line <= 2:
        if next_line is not None and cursor >= next_line:
            if _date_matches(lines[cursor][2]):
                diagnostics["boundary_rejection_count"] += 1
            break
        line_text = lines[cursor][2]
        issuer_in_line = issuer_hit is not None and lines[cursor][0] <= issuer_hit.start() < lines[cursor][1]
        if not _date_matches(line_text) and not issuer_in_line:
            break
        last_line = cursor
        cursor += 1

    left = lines[first_line][0]
    right = lines[last_line][1]
    return left, right


def _certificate_candidates(certificates, index, source_text):
    text = _certificate_source_text(source_text)
    lines = _line_spans(text)
    diagnostics = _certificate_match_diagnostics()
    if not lines:
        _raise_certificate(SOURCE_DATE_UNMATCHED, index, NO_NAME_ANCHOR, diagnostics)

    record = certificates[index]
    name_pattern = phrase_pattern(record.get("name") or "")
    name_hits = list(re.finditer(name_pattern, text, re.I))
    diagnostics["name_anchor_count"] = len(name_hits)
    if not name_hits:
        _raise_certificate(SOURCE_DATE_UNMATCHED, index, NO_NAME_ANCHOR, diagnostics)

    organization = record.get("organization") or ""
    organization_pattern = phrase_pattern(organization)
    issuer_hits = list(re.finditer(organization_pattern, text, re.I)) if organization else []
    diagnostics["issuer_anchor_count"] = len(issuer_hits)
    anchors = _all_certificate_anchors(certificates, text)
    candidates = []
    ambiguous_evidence = False
    local_issuer_mismatch = False

    for name_hit in name_hits:
        anchor_position = anchors.index((name_hit.start(), name_hit.end()))
        previous_anchor = anchors[anchor_position - 1] if anchor_position else None
        next_anchor = anchors[anchor_position + 1] if anchor_position + 1 < len(anchors) else None
        name_line = _line_index(lines, name_hit.start())
        if any(
            span != (name_hit.start(), name_hit.end())
            and _line_index(lines, span[0]) == name_line
            for span in anchors
        ):
            diagnostics["boundary_rejection_count"] += 1
            continue

        local_issuers = _adjacent_identity_hits(
            organization_pattern if organization else "",
            text,
            lines,
            name_hit,
            previous_anchor,
            next_anchor,
        )
        unique_name_only = bool(organization and not issuer_hits and len(name_hits) == 1)
        if organization and len(local_issuers) != 1 and not unique_name_only:
            if len(local_issuers) > 1:
                diagnostics["ambiguous_candidate_count"] += 1
            else:
                local_issuer_mismatch = True
            continue
        issuer_hit = local_issuers[0] if local_issuers else None
        left, right = _certificate_record_span(
            text,
            lines,
            name_hit,
            issuer_hit,
            previous_anchor,
            next_anchor,
            diagnostics,
        )
        segment = text[left:right]
        evidence, error = _certificate_evidence(segment, diagnostics)
        diagnostics["candidate_span_count"] += 1
        local_name_start = name_hit.start() - left
        local_name_end = name_hit.end() - left
        line_start, line_end, _ = lines[name_line]
        for date_hit in _date_matches(segment):
            diagnostics["candidate_date_count"] += 1
            absolute_start = left + date_hit.start()
            if line_start <= absolute_start < line_end:
                diagnostics["date_inline_count"] += 1
            if date_hit.end() <= local_name_start:
                diagnostics["date_before_name_count"] += 1
            elif date_hit.start() >= local_name_end:
                diagnostics["date_after_name_count"] += 1
        if evidence is None:
            if error == SOURCE_DATE_AMBIGUOUS:
                diagnostics["ambiguous_candidate_count"] += 1
                ambiguous_evidence = True
            elif error == UNSUPPORTED_DATE_PATTERN:
                _raise_certificate(error, index, UNSUPPORTED_LAYOUT, diagnostics)
            continue
        issue, expiration, local_span, status = evidence
        absolute_span = (left + local_span[0], left + local_span[1])
        signature = (str(_serialized(issue)), str(_serialized(expiration)))
        candidates.append((signature, issue, expiration, absolute_span, status, diagnostics))

    is_identity_unique = len(name_hits) == 1 or (
        organization and len(issuer_hits) == 1 and not local_issuer_mismatch
    )

    if ambiguous_evidence:
        if is_identity_unique:
            fallback_span = (name_hits[0].start(), name_hits[0].end())
            diagnostics["safe_detail"] = MULTIPLE_LOCAL_DATE_MAPPINGS
            return (None, None, None, fallback_span, AMBIGUOUS_OPTIONAL_DATE_OMITTED, diagnostics), text
        _raise_certificate(
            SOURCE_DATE_AMBIGUOUS,
            index,
            MULTIPLE_LOCAL_DATE_MAPPINGS,
            diagnostics,
        )

    if not candidates:
        if local_issuer_mismatch or (organization and not issuer_hits and len(name_hits) != 1):
            detail = NO_ISSUER_ANCHOR
            _raise_certificate(SOURCE_DATE_UNMATCHED, index, detail, diagnostics)
        elif len(name_hits) > 1 and not organization:
            _raise_certificate(SOURCE_DATE_AMBIGUOUS, index, IDENTITY_NOT_UNIQUE, diagnostics)
        else:
            if diagnostics["boundary_rejection_count"]:
                detail = DATE_OUTSIDE_RECORD_BOUNDARY
            elif diagnostics["candidate_span_count"] and not diagnostics["candidate_date_count"]:
                detail = NO_LOCAL_DATE_EVIDENCE
            else:
                detail = UNSUPPORTED_LAYOUT

            if is_identity_unique:
                fallback_span = (name_hits[0].start(), name_hits[0].end())
                diagnostics["safe_detail"] = detail
                return (None, None, None, fallback_span, UNVERIFIED_OPTIONAL_DATE_OMITTED, diagnostics), text

            _raise_certificate(SOURCE_DATE_UNMATCHED, index, detail, diagnostics)

    if len(candidates) != 1:
        diagnostics["ambiguous_candidate_count"] += len(candidates)
        _raise_certificate(SOURCE_DATE_AMBIGUOUS, index, IDENTITY_NOT_UNIQUE, diagnostics)
    return candidates[0], text


def _certificate_resolution(source_text, payload, audit, omissions):
    certificates = payload.get("certificates", [])
    for index, item in enumerate(certificates):
        if not isinstance(item, dict):
            continue
        has_dates = item.get("issue_date") is not None or item.get("expiration_date") is not None
        if not has_dates:
            continue
        invalid = _invalid_pair(item.get("issue_date"), item.get("expiration_date"))
        if not invalid:
            name_pattern = phrase_pattern(item.get("name") or "")
            if not name_pattern or name_pattern == r"(?!)":
                continue
            text = _certificate_source_text(source_text)
            if not list(re.finditer(name_pattern, text, re.I)):
                continue

        candidate, normalized_source = _certificate_candidates(certificates, index, source_text)
        signature, issue, expiration, span, status, matcher = candidate
        if isinstance(issue, OpenEndedDate):
            raise SourceDateResolutionError(UNSUPPORTED_DATE_PATTERN, "certificates", index)
        if issue is not None and expiration is not None and definitely_reversed(issue, expiration):
            raise SourceDateResolutionError(SOURCE_DATA_CONFLICT, "certificates", index)

        old_issue = item.get("issue_date")
        old_expiration = item.get("expiration_date")

        issue_omitted = False
        expiration_omitted = False

        if status in (UNVERIFIED_OPTIONAL_DATE_OMITTED, AMBIGUOUS_OPTIONAL_DATE_OMITTED):
            if old_issue is not None:
                omissions["issue_date_omitted_count"] += 1
                omissions["certificate_date_omitted_count"] += 1
                issue_omitted = True
            if old_expiration is not None:
                omissions["expiration_date_omitted_count"] += 1
                omissions["certificate_date_omitted_count"] += 1
                expiration_omitted = True
            item["issue_date"] = None
            item["expiration_date"] = None
            reason = (
                SOURCE_DATE_AMBIGUOUS_OMITTED
                if status == AMBIGUOUS_OPTIONAL_DATE_OMITTED
                else SOURCE_DATE_UNMATCHED_OMITTED
            )
            detail_reason = matcher.get(
                "safe_detail",
                MULTIPLE_LOCAL_DATE_MAPPINGS if status == AMBIGUOUS_OPTIONAL_DATE_OMITTED else NO_LOCAL_DATE_EVIDENCE,
            )
            affected = []
            if issue_omitted:
                affected.append("issue_date")
            if expiration_omitted:
                affected.append("expiration_date")
            audit.append(_safe_audit(
                "certificates", index, status,
                tuple(affected or ("issue_date", "expiration_date")), span, normalized_source,
                matcher=matcher,
                reason=reason,
                detail_reason=detail_reason,
            ))
            continue

        if issue is None and old_issue is not None:
            omissions["issue_date_omitted_count"] += 1
            omissions["certificate_date_omitted_count"] += 1
            issue_omitted = True
        if expiration is None and old_expiration is not None:
            omissions["expiration_date_omitted_count"] += 1
            omissions["certificate_date_omitted_count"] += 1
            expiration_omitted = True

        item["issue_date"] = _serialized(issue)
        item["expiration_date"] = _serialized(expiration)
        affected = []
        if issue is not None:
            affected.append("issue_date")
        if expiration is not None:
            affected.append("expiration_date")
        if issue_omitted:
            affected.append("issue_date")
        if expiration_omitted:
            affected.append("expiration_date")

        reason = None
        detail_reason = None
        if issue_omitted or expiration_omitted:
            is_ambiguous = (issue_omitted and matcher.get("issue_ambiguous")) or (
                expiration_omitted and matcher.get("expiration_ambiguous")
            )
            reason = SOURCE_DATE_AMBIGUOUS_OMITTED if is_ambiguous else SOURCE_DATE_UNMATCHED_OMITTED
            detail_reason = MULTIPLE_LOCAL_DATE_MAPPINGS if is_ambiguous else NO_LOCAL_DATE_EVIDENCE
        audit.append(_safe_audit(
            "certificates", index, status,
            tuple(sorted(set(affected)) or ("issue_date", "expiration_date")), span, normalized_source,
            matcher=matcher,
            reason=reason,
            detail_reason=detail_reason,
        ))


def reconcile_source_grounded_dates(source_text: str, value: object) -> SourceDateResolution:
    """Return a reconciled copy plus internal proof/audit; input remains untouched."""

    if not isinstance(value, dict):
        raise ValueError("STRUCTURED_OBJECT_REQUIRED")
    payload = copy.deepcopy(value)
    audit = []
    proofs = set()
    omissions = {
        "certificate_date_omitted_count": 0,
        "issue_date_omitted_count": 0,
        "expiration_date_omitted_count": 0,
    }
    _experience_resolution(source_text, payload, proofs, audit)
    _certificate_resolution(source_text, payload, audit, omissions)
    context = {"source_conflict_proof": VerifiedSourceConflicts(frozenset(proofs))}
    return SourceDateResolution(payload, context, tuple(audit), dict(omissions))
