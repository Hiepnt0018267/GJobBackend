import asyncio
import copy
import json

import pytest

from app.schemas.cv_extraction_wire import (
    CVExtractionProviderResponse,
    validate_reconciled_provider_response,
)
from app.services.cv_source_date_reconciliation import (
    AMBIGUOUS_OPTIONAL_DATE_OMITTED,
    DATE_OUTSIDE_RECORD_BOUNDARY,
    IDENTITY_NOT_UNIQUE,
    MULTIPLE_LOCAL_DATE_MAPPINGS,
    NO_ISSUER_ANCHOR,
    NO_LOCAL_DATE_EVIDENCE,
    NO_NAME_ANCHOR,
    RESOLVED_CERTIFICATE_EXPIRATION,
    RESOLVED_CERTIFICATE_ISSUE_DATE,
    RESOLVED_EXPLICIT_RANGE,
    SOURCE_DATA_CONFLICT,
    SOURCE_DATE_AMBIGUOUS,
    SOURCE_DATE_AMBIGUOUS_OMITTED,
    SOURCE_DATE_UNMATCHED,
    SOURCE_DATE_UNMATCHED_OMITTED,
    UNSUPPORTED_DATE_PATTERN,
    UNVERIFIED_OPTIONAL_DATE_OMITTED,
    SourceDateResolutionError,
    reconcile_source_grounded_dates,
)
from app.services.cv_structured_extraction_service import (
    CVExtractionCorrectionError,
    CVStructuredExtractionService,
)


def certificate(name="AWS Certified Developer", organization="Amazon", **dates):
    return {"name": name, "organization": organization, **dates}


def invalid(name="AWS Certified Developer", organization="Amazon", **extra):
    return certificate(
        name,
        organization,
        issue_date="2025",
        expiration_date="2022",
        **extra,
    )


def resolve(source, records):
    wire = CVExtractionProviderResponse.model_validate({"certificates": records})
    result = reconcile_source_grounded_dates(
        source,
        wire.model_dump(mode="json", exclude_unset=True),
    )
    canonical = validate_reconciled_provider_response(
        result.payload,
        validation_context=result.validation_context,
    )
    return result, canonical


def test_date_before_name_on_same_line():
    result, canonical = resolve("2022 — AWS Certified Developer — Amazon", [invalid()])
    item = canonical.certificates[0]
    assert item.issue_date.year == 2022 and item.expiration_date is None
    assert result.audit[0]["matcher"]["date_before_name_count"] == 1
    assert result.audit[0]["matcher"]["date_inline_count"] == 1


def test_date_before_name_on_previous_line_for_unique_record():
    result, canonical = resolve("2022\nAWS Certified Developer\nAmazon", [invalid()])
    assert canonical.certificates[0].issue_date.year == 2022
    assert result.audit[0]["matcher"]["date_before_name_count"] == 1


def test_date_after_name_on_next_line():
    result, canonical = resolve("AWS Certified Developer\nAmazon\nIssued 2022", [invalid()])
    assert canonical.certificates[0].issue_date.year == 2022
    assert result.audit[0]["matcher"]["date_after_name_count"] == 1


def test_date_inline_after_issuer():
    result, canonical = resolve("AWS Certified Developer | Amazon | 2022", [invalid()])
    assert canonical.certificates[0].issue_date.year == 2022
    assert result.audit[0]["matcher"]["date_inline_count"] == 1


def test_issuer_before_name_is_supported():
    _, canonical = resolve("Amazon\nAWS Certified Developer\nIssued 2022", [invalid()])
    assert canonical.certificates[0].issue_date.year == 2022


def test_issuer_after_name_is_supported():
    _, canonical = resolve("AWS Certified Developer\nAmazon\nIssued 2022", [invalid()])
    assert canonical.certificates[0].issue_date.year == 2022


def test_two_date_before_name_records_do_not_cross_map():
    records = [invalid("Certificate A", "Issuer A"), invalid("Certificate B", "Issuer B")]
    _, canonical = resolve(
        "2022 — Certificate A — Issuer A\n2023 — Certificate B — Issuer B",
        records,
    )
    assert [item.issue_date.year for item in canonical.certificates] == [2022, 2023]


def test_same_name_different_issuers_use_issuer_evidence():
    records = [invalid("Certificate X", "Issuer A"), invalid("Certificate X", "Issuer B")]
    _, canonical = resolve(
        "Certificate X — Issuer A — 2022\nCertificate X — Issuer B — 2023",
        records,
    )
    assert [item.issue_date.year for item in canonical.certificates] == [2022, 2023]


def test_dates_between_two_anchors_are_gracefully_omitted():
    records = [invalid("Certificate A", None), invalid("Certificate B", None)]
    result, canonical = resolve(
        "Certificate A\n2022\n2023\nCertificate B",
        records,
    )
    assert len(canonical.certificates) == 2
    assert canonical.certificates[0].name == "Certificate A"
    assert canonical.certificates[0].issue_date is None
    assert canonical.certificates[0].expiration_date is None
    assert canonical.certificates[1].name == "Certificate B"
    assert canonical.certificates[1].issue_date is None
    assert canonical.certificates[1].expiration_date is None
    assert result.audit[0]["status"] == AMBIGUOUS_OPTIONAL_DATE_OMITTED
    assert result.audit[0]["reason"] == SOURCE_DATE_AMBIGUOUS_OMITTED
    assert result.audit[0]["detail_reason"] == MULTIPLE_LOCAL_DATE_MAPPINGS
    assert result.diagnostics["certificate_date_omitted_count"] == 4


def test_record_must_not_steal_previous_certificate_date():
    records = [
        certificate("Certificate A", None, issue_date="2022", expiration_date=None),
        invalid("Certificate B", None),
    ]
    result, canonical = resolve(
        "Certificate A\n2022\nCertificate B",
        records,
    )
    assert len(canonical.certificates) == 2
    assert canonical.certificates[0].issue_date.year == 2022
    assert canonical.certificates[1].issue_date is None
    assert canonical.certificates[1].expiration_date is None
    assert canonical.certificates[1].name == "Certificate B"
    assert result.audit[0]["status"] == RESOLVED_CERTIFICATE_ISSUE_DATE
    assert result.audit[1]["status"] == UNVERIFIED_OPTIONAL_DATE_OMITTED
    assert result.audit[1]["reason"] == SOURCE_DATE_UNMATCHED_OMITTED
    assert result.audit[1]["detail_reason"] == DATE_OUTSIDE_RECORD_BOUNDARY
    assert result.diagnostics["certificate_date_omitted_count"] == 2


def test_record_must_not_steal_next_certificate_date():
    records = [
        invalid("Certificate A", None),
        certificate("Certificate B", None, issue_date="2023", expiration_date=None),
    ]
    result, canonical = resolve(
        "Certificate A\nCertificate B\n2023",
        records,
    )
    assert len(canonical.certificates) == 2
    assert canonical.certificates[0].issue_date is None
    assert canonical.certificates[0].expiration_date is None
    assert canonical.certificates[0].name == "Certificate A"
    assert canonical.certificates[1].issue_date.year == 2023
    assert result.audit[0]["status"] == UNVERIFIED_OPTIONAL_DATE_OMITTED
    assert result.audit[0]["detail_reason"] == NO_LOCAL_DATE_EVIDENCE
    assert result.audit[1]["status"] == RESOLVED_CERTIFICATE_ISSUE_DATE


def test_single_date_is_issue_date_only():
    result, canonical = resolve("AWS Certified Developer, 2022", [invalid()])
    item = canonical.certificates[0]
    assert item.issue_date.year == 2022 and item.expiration_date is None
    assert result.audit[0]["status"] == RESOLVED_CERTIFICATE_ISSUE_DATE


def test_explicit_issued_and_expires():
    result, canonical = resolve(
        "AWS Certified Developer Amazon issued 2022 expires 2025",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert (item.issue_date.year, item.expiration_date.year) == (2022, 2025)
    assert result.audit[0]["status"] == RESOLVED_CERTIFICATE_EXPIRATION


def test_explicit_validity_range():
    result, canonical = resolve("2022 - 2025 | AWS Certified Developer | Amazon", [invalid()])
    item = canonical.certificates[0]
    assert (item.issue_date.year, item.expiration_date.year) == (2022, 2025)
    assert result.audit[0]["status"] == RESOLVED_EXPLICIT_RANGE


def test_present_cannot_become_issue_date():
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates(
            "Present — AWS Certified Developer — Amazon",
            {"certificates": [invalid()]},
        )
    assert caught.value.code == UNSUPPORTED_DATE_PATTERN


def test_no_local_date_evidence_is_gracefully_omitted():
    result, canonical = resolve(
        "AWS Certified Developer — Amazon",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.name == "AWS Certified Developer"
    assert item.organization == "Amazon"
    assert item.issue_date is None
    assert item.expiration_date is None
    assert result.audit[0]["status"] == UNVERIFIED_OPTIONAL_DATE_OMITTED
    assert result.audit[0]["reason"] == SOURCE_DATE_UNMATCHED_OMITTED
    assert result.audit[0]["detail_reason"] == NO_LOCAL_DATE_EVIDENCE
    assert result.diagnostics["issue_date_omitted_count"] == 1
    assert result.diagnostics["expiration_date_omitted_count"] == 1
    assert result.diagnostics["certificate_date_omitted_count"] == 2


def test_unique_name_can_match_when_source_issuer_is_absent():
    result, canonical = resolve("2022 — AWS Certified Developer", [invalid()])
    assert canonical.certificates[0].issue_date.year == 2022
    assert result.audit[0]["matcher"]["issuer_anchor_count"] == 0


def test_issuer_present_only_outside_local_record_is_rejected_safely():
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates(
            "Amazon\nUnrelated section\nUnrelated section\n2022 — AWS Certified Developer",
            {"certificates": [invalid()]},
        )
    assert caught.value.code == SOURCE_DATE_UNMATCHED
    assert caught.value.detail_code == NO_ISSUER_ANCHOR


def test_multiple_equally_valid_dates_are_gracefully_omitted():
    result, canonical = resolve(
        "AWS Certified Developer Amazon issued 2021 and issued 2022",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.issue_date is None and item.expiration_date is None
    assert item.name == "AWS Certified Developer"
    assert result.audit[0]["status"] == AMBIGUOUS_OPTIONAL_DATE_OMITTED
    assert result.audit[0]["reason"] == SOURCE_DATE_AMBIGUOUS_OMITTED
    assert result.audit[0]["detail_reason"] == MULTIPLE_LOCAL_DATE_MAPPINGS


def test_repeated_name_without_issuer_is_identity_ambiguous():
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates(
            "Certificate X 2022\nCertificate X 2023",
            {"certificates": [invalid("Certificate X", None)]},
        )
    assert caught.value.code == SOURCE_DATE_AMBIGUOUS
    assert caught.value.detail_code == IDENTITY_NOT_UNIQUE


def test_existing_valid_certificate_is_exact_noop_and_idempotent():
    payload = {"certificates": [certificate(issue_date="2022", expiration_date="2025")]}
    first = reconcile_source_grounded_dates("Unrelated source", payload)
    second = reconcile_source_grounded_dates("Unrelated source", first.payload)
    assert first.payload == payload == second.payload
    assert first.audit == second.audit == ()


def test_unrelated_certificate_fields_are_preserved():
    record = invalid(credential_url="https://example.test/cert")
    before = copy.deepcopy(record)
    _, canonical = resolve("2022 — AWS Certified Developer — Amazon", [record])
    item = canonical.certificates[0]
    assert item.name == before["name"]
    assert item.organization == before["organization"]
    assert str(item.credential_url) == before["credential_url"]


def test_punctuation_case_and_separator_normalization_is_deterministic():
    record = invalid("AWS Certified Developer - Associate", "Amazon Web Services")
    _, canonical = resolve(
        "2022 • aws certified developer — associate • AMAZON WEB SERVICES",
        [record],
    )
    assert canonical.certificates[0].issue_date.year == 2022


class OneCallProvider:
    def __init__(self):
        self.calls = 0

    async def generate_structured(self, **kwargs):
        self.calls += 1
        return CVExtractionProviderResponse.model_validate({"certificates": [invalid()]})


def test_service_succeeds_with_graceful_omission_and_exposes_only_safe_diagnostics(caplog):
    provider = OneCallProvider()
    service = CVStructuredExtractionService(provider=provider)
    source = "AWS Certified Developer — Amazon"
    result = asyncio.run(service.extract_from_text(source))
    assert len(result.certificates) == 1
    item = result.certificates[0]
    assert item.name == "AWS Certified Developer"
    assert item.issue_date is None and item.expiration_date is None
    diagnostic = service.last_diagnostics.date_resolution
    assert provider.calls == 1 and service.schema_retries == 0
    assert diagnostic["status"] == "resolved"
    assert diagnostic["certificate_date_omitted_count"] == 2
    assert diagnostic["issue_date_omitted_count"] == 1
    assert diagnostic["expiration_date_omitted_count"] == 1
    assert diagnostic["items"][0]["status"] == UNVERIFIED_OPTIONAL_DATE_OMITTED
    assert diagnostic["items"][0]["detail_reason"] == NO_LOCAL_DATE_EVIDENCE
    assert set(diagnostic["items"][0]["matcher"]) == {
        "name_anchor_count", "issuer_anchor_count", "candidate_span_count",
        "date_before_name_count", "date_inline_count", "date_after_name_count",
        "candidate_date_count", "ambiguous_candidate_count", "boundary_rejection_count",
        "safe_detail",
    }
    serialized = json.dumps(diagnostic)
    assert "AWS" not in serialized and "Amazon" not in serialized
    assert source not in caplog.text and "AWS" not in caplog.text and "Amazon" not in caplog.text


def test_service_strict_failure_on_unmatched_certificate_identity():
    provider = OneCallProvider()
    service = CVStructuredExtractionService(provider=provider)
    source = "Software Engineer with generic experience and no certs"
    with pytest.raises(CVExtractionCorrectionError):
        asyncio.run(service.extract_from_text(source))
    diagnostic = service.last_diagnostics.date_resolution
    assert diagnostic["status"] == "failed"
    assert diagnostic["reason"] == SOURCE_DATE_UNMATCHED
    assert diagnostic["detail_reason"] == NO_NAME_ANCHOR


def test_certificate_identity_matched_issue_unmatched_expiration_kept():
    result, canonical = resolve(
        "AWS Certified Developer Amazon expires Jan 2025",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.name == "AWS Certified Developer"
    assert item.issue_date is None
    assert item.expiration_date.year == 2025 and item.expiration_date.month == 1
    assert result.diagnostics["issue_date_omitted_count"] == 1
    assert result.diagnostics["expiration_date_omitted_count"] == 0
    assert result.diagnostics["certificate_date_omitted_count"] == 1


def test_certificate_identity_matched_expiration_unmatched_issue_kept():
    result, canonical = resolve(
        "AWS Certified Developer Amazon issued Jan 2022",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.name == "AWS Certified Developer"
    assert item.issue_date.year == 2022 and item.issue_date.month == 1
    assert item.expiration_date is None
    assert result.diagnostics["issue_date_omitted_count"] == 0
    assert result.diagnostics["expiration_date_omitted_count"] == 1
    assert result.diagnostics["certificate_date_omitted_count"] == 1


def test_certificate_both_dates_unmatched():
    result, canonical = resolve(
        "AWS Certified Developer Amazon credential verification",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.name == "AWS Certified Developer"
    assert item.issue_date is None
    assert item.expiration_date is None
    assert result.diagnostics["certificate_date_omitted_count"] == 2


def test_certificate_partial_verified_provider_valid_dates():
    payload = {"certificates": [certificate(issue_date="2022", expiration_date="2025")]}
    result = reconcile_source_grounded_dates("AWS Certified Developer Amazon issued 2022", payload)
    item = result.payload["certificates"][0]
    assert item["issue_date"]["year"] == 2022 and item["issue_date"]["precision"] == "year"
    assert item["expiration_date"] is None
    assert result.diagnostics["issue_date_omitted_count"] == 0
    assert result.diagnostics["expiration_date_omitted_count"] == 1
    assert result.diagnostics["certificate_date_omitted_count"] == 1


def test_certificate_expiration_ambiguous():
    result, canonical = resolve(
        "AWS Certified Developer Amazon issued 2022 expires 2024 and expires 2025",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.issue_date.year == 2022
    assert item.expiration_date is None
    assert result.diagnostics["expiration_date_omitted_count"] == 1


def test_certificate_issue_ambiguous():
    result, canonical = resolve(
        "AWS Certified Developer Amazon issued 2021 and issued 2022 expires 2025",
        [invalid()],
    )
    item = canonical.certificates[0]
    assert item.issue_date is None
    assert item.expiration_date.year == 2025
    assert result.diagnostics["issue_date_omitted_count"] == 1
    assert result.diagnostics["expiration_date_omitted_count"] == 0


def test_certificate_source_data_conflict_remains_strict():
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates(
            "AWS Certified Developer Amazon issued 2025 expires 2022",
            {"certificates": [invalid()]},
        )
    assert caught.value.code == SOURCE_DATA_CONFLICT


def test_certificate_identity_unmatched_remains_strict():
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates(
            "Unrelated document without developer certification",
            {"certificates": [invalid()]},
        )
    assert caught.value.code == SOURCE_DATE_UNMATCHED
    assert caught.value.detail_code == NO_NAME_ANCHOR


def test_certificate_no_dates_originally_unchanged():
    payload = {"certificates": [certificate("AWS Certified Developer", "Amazon")]}
    result = reconcile_source_grounded_dates("AWS Certified Developer Amazon 2022", payload)
    assert result.payload == payload
    assert result.audit == ()
    assert result.diagnostics["certificate_date_omitted_count"] == 0


def test_three_certificates_matrix_section_21():
    records = [
        invalid("Cert Alpha", "Org A"),
        invalid("Cert Beta", "Org B"),
        invalid("Cert Gamma", "Org C"),
    ]
    source = (
        "Cert Alpha Org A expires 2025\n"
        "Cert Beta Org B issued 2022\n"
        "Cert Gamma Org C 2022 - 2025"
    )
    result, canonical = resolve(source, records)
    assert len(canonical.certificates) == 3
    alpha, beta, gamma = canonical.certificates
    assert alpha.issue_date is None and alpha.expiration_date.year == 2025
    assert beta.issue_date.year == 2022 and beta.expiration_date is None
    assert gamma.issue_date.year == 2022 and gamma.expiration_date.year == 2025
    assert result.diagnostics["issue_date_omitted_count"] == 1
    assert result.diagnostics["expiration_date_omitted_count"] == 1
    assert result.diagnostics["certificate_date_omitted_count"] == 2


def test_certificate_idempotence_preserves_payload_and_empty_second_audit():
    payload = {"certificates": [invalid()]}
    first = reconcile_source_grounded_dates("AWS Certified Developer Amazon", payload)
    assert first.payload["certificates"][0]["issue_date"] is None
    assert first.payload["certificates"][0]["expiration_date"] is None
    second = reconcile_source_grounded_dates("AWS Certified Developer Amazon", first.payload)
    assert second.payload == first.payload
    assert second.audit == ()
    assert second.diagnostics["certificate_date_omitted_count"] == 0
