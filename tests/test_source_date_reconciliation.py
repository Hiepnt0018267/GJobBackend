import asyncio
import copy
import json

import httpx
import pytest

from app.ai.exceptions import AITokenAccountingUnavailableError
from app.ai.ollama_provider import OllamaProvider
from app.schemas.cv_extraction_wire import (
    CVExtractionProviderResponse,
    validate_reconciled_provider_response,
)
from app.services.cv_source_date_reconciliation import (
    AMBIGUOUS_OPTIONAL_DATE_OMITTED,
    RESOLVED_CERTIFICATE_EXPIRATION,
    RESOLVED_CERTIFICATE_ISSUE_DATE,
    RESOLVED_EXPLICIT_RANGE,
    RESOLVED_OPEN_ENDED_RANGE,
    SOURCE_DATA_CONFLICT,
    SOURCE_DATE_AMBIGUOUS,
    SOURCE_DATE_UNMATCHED,
    UNSUPPORTED_DATE_PATTERN,
    UNVERIFIED_OPTIONAL_DATE_OMITTED,
    SourceDateResolutionError,
    reconcile_source_grounded_dates,
)
from app.services.cv_structured_extraction_service import (
    CVExtractionCorrectionError,
    CVStructuredExtractionService,
)


def experience(position="Engineer", company="Acme", description="Build APIs", **dates):
    return {"position": position, "company_name": company, "description": description, **dates}


def certificate(name="Cloud Certificate", organization="Issuer", **dates):
    return {"name": name, "organization": organization, **dates}


def resolve(source, payload):
    wire = CVExtractionProviderResponse.model_validate(payload)
    result = reconcile_source_grounded_dates(source, wire.model_dump(mode="json", exclude_unset=True))
    canonical = validate_reconciled_provider_response(
        result.payload,
        validation_context=result.validation_context,
    )
    return result, canonical


def test_experience_reversed_explicit_range_is_source_corrected_with_precision():
    payload = {"experiences": [experience(start_date="12/2023", end_date="01/2022")]}
    result, canonical = resolve("Experience 01/2022 - 12/2023 Engineer Acme Build APIs", payload)
    item = canonical.experiences[0]
    assert (item.start_date.year, item.start_date.month, item.start_date.precision) == (2022, 1, "month")
    assert (item.end_date.year, item.end_date.month, item.end_date.precision) == (2023, 12, "month")
    assert result.audit[0]["status"] == RESOLVED_EXPLICIT_RANGE


def test_experience_open_ended_source_uses_current_without_calendar_date():
    payload = {"experiences": [experience(start_date="2024", end_date="2021")]}
    result, canonical = resolve("Experience March 2021 to Present Engineer Acme Build APIs", payload)
    item = canonical.experiences[0]
    assert item.start_date.precision == "month" and item.start_date.month == 3
    assert item.end_date.state == "current" and item.is_current is True
    assert result.audit[0]["status"] == RESOLVED_OPEN_ENDED_RANGE


def test_same_company_different_positions_map_to_their_own_ranges():
    payload = {"experiences": [
        experience("Senior Engineer", start_date="2024", end_date="2022"),
        experience("Data Analyst", description="Analyze data", start_date="2021", end_date="2019"),
    ]}
    source = ("2022 to 2024 Senior Engineer Acme Build APIs "
              "2019 to 2021 Data Analyst Acme Analyze data")
    _, canonical = resolve(source, payload)
    assert [item.start_date.year for item in canonical.experiences] == [2022, 2019]
    assert [item.end_date.year for item in canonical.experiences] == [2024, 2021]


def test_source_conflict_is_preserved_with_internal_proof_not_fabricated():
    payload = {"experiences": [experience(start_date="2024", end_date="2021")]}
    result, canonical = resolve("2024 to 2021 Engineer Acme Build APIs", payload)
    item = canonical.experiences[0]
    assert item.start_date.year == 2024 and item.end_date.year == 2021
    assert item.date_consistency.state == SOURCE_DATA_CONFLICT
    assert result.audit[0]["status"] == SOURCE_DATA_CONFLICT


def test_ambiguous_experience_is_typed_and_never_swapped_nulled_or_dropped():
    payload = {"experiences": [experience(start_date="2024", end_date="2021")]}
    before = copy.deepcopy(payload)
    source = "2020 to 2022 Engineer Acme Build APIs 2021 to 2023 Engineer Acme Build APIs"
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates(source, payload)
    assert caught.value.code == SOURCE_DATE_AMBIGUOUS
    assert payload == before and len(payload["experiences"]) == 1
    assert payload["experiences"][0]["end_date"] == "2021"


def test_unmatched_experience_is_typed_without_mutation():
    payload = {"experiences": [experience(start_date="2024", end_date="2021")]}
    before = copy.deepcopy(payload)
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates("Engineer Acme dates unavailable Build APIs", payload)
    assert caught.value.code == SOURCE_DATE_UNMATCHED and payload == before


def test_certificate_single_date_is_issue_date_and_source_grounded_omission():
    payload = {"certificates": [certificate(start_date=None, issue_date="2025", expiration_date="2022")]}
    payload["certificates"][0].pop("start_date")
    result, canonical = resolve("Cloud Certificate Issuer Issued May 2023", payload)
    item = canonical.certificates[0]
    assert item.issue_date.year == 2023 and item.issue_date.month == 5
    assert item.expiration_date is None
    assert result.audit[0]["status"] == RESOLVED_CERTIFICATE_ISSUE_DATE


def test_certificate_issued_and_expiration_keywords_are_independent():
    payload = {"certificates": [certificate(issue_date="2025", expiration_date="2022")]}
    result, canonical = resolve(
        "Cloud Certificate Issuer issued Jan 2022, expires Jan 2025",
        payload,
    )
    item = canonical.certificates[0]
    assert (item.issue_date.year, item.expiration_date.year) == (2022, 2025)
    assert result.audit[0]["status"] == RESOLVED_CERTIFICATE_EXPIRATION


def test_certificate_explicit_validity_range_preserves_year_precision():
    payload = {"certificates": [certificate(issue_date="2025", expiration_date="2022")]}
    result, canonical = resolve("Cloud Certificate Issuer validity 2022 - 2025", payload)
    item = canonical.certificates[0]
    assert item.issue_date.precision == item.expiration_date.precision == "year"
    assert result.audit[0]["status"] == RESOLVED_EXPLICIT_RANGE


def test_certificate_explicit_open_ended_range_uses_canonical_current_semantics():
    payload = {"certificates": [certificate(issue_date="2025", expiration_date="2022")]}
    result, canonical = resolve("Cloud Certificate Issuer validity 2022 - Present", payload)
    item = canonical.certificates[0]
    assert item.issue_date.year == 2022
    assert item.expiration_date.state == "current"
    assert result.audit[0]["status"] == RESOLVED_OPEN_ENDED_RANGE


def test_certificate_present_cannot_become_issue_date():
    payload = {"certificates": [certificate(issue_date="2025", expiration_date="2022")]}
    with pytest.raises(SourceDateResolutionError) as caught:
        reconcile_source_grounded_dates("Cloud Certificate Issuer issued Present", payload)
    assert caught.value.code == UNSUPPORTED_DATE_PATTERN


def test_three_certificates_reconcile_independently_without_cross_contamination():
    payload = {"certificates": [
        certificate("Alpha", "Org A", issue_date="2025", expiration_date="2021"),
        certificate("Beta", "Org B", issue_date="2026", expiration_date="2022"),
        certificate("Gamma", "Org C", issue_date="2027", expiration_date="2023"),
    ]}
    source = ("Alpha Org A issued 2021 expires 2025\n"
              "Beta Org B issued 2022 expires 2026\n"
              "Gamma Org C issued 2023 expires 2027")
    result, canonical = resolve(source, payload)
    assert len(canonical.certificates) == 3
    assert [(item.issue_date.year, item.expiration_date.year) for item in canonical.certificates] == [
        (2021, 2025), (2022, 2026), (2023, 2027)]
    assert len(result.audit) == 3


def test_same_certificate_name_different_issuers_do_not_cross_map():
    payload = {"certificates": [
        certificate("Cloud Pro", "Issuer One", issue_date="2025", expiration_date="2021"),
        certificate("Cloud Pro", "Issuer Two", issue_date="2026", expiration_date="2022"),
    ]}
    source = ("Cloud Pro Issuer One issued 2021 expires 2025\n"
              "Cloud Pro Issuer Two issued 2022 expires 2026")
    _, canonical = resolve(source, payload)
    assert len(canonical.certificates) == 2
    assert [(item.issue_date.year, item.expiration_date.year) for item in canonical.certificates] == [
        (2021, 2025), (2022, 2026)]


def test_certificate_source_conflict_and_unmatched_provider_date_fail_typed():
    payload = {"certificates": [certificate(issue_date="2025", expiration_date="2022")]}
    with pytest.raises(SourceDateResolutionError) as conflict:
        reconcile_source_grounded_dates("Cloud Certificate Issuer validity 2025 - 2022", payload)
    assert conflict.value.code == SOURCE_DATA_CONFLICT
    result = reconcile_source_grounded_dates("Cloud Certificate Issuer no date evidence", payload)
    item = result.payload["certificates"][0]
    assert item["issue_date"] is None and item["expiration_date"] is None
    assert result.audit[0]["status"] == UNVERIFIED_OPTIONAL_DATE_OMITTED
    assert result.diagnostics["certificate_date_omitted_count"] == 2


def test_certificate_multiple_distinct_issue_dates_are_ambiguous_not_guessed():
    payload = {"certificates": [certificate(issue_date="2025", expiration_date="2022")]}
    result = reconcile_source_grounded_dates(
        "Cloud Certificate Issuer issued 2021 and issued 2022",
        payload,
    )
    item = result.payload["certificates"][0]
    assert item["issue_date"] is None and item["expiration_date"] is None
    assert result.audit[0]["status"] == AMBIGUOUS_OPTIONAL_DATE_OMITTED
    assert result.diagnostics["certificate_date_omitted_count"] == 2


def test_valid_payload_is_noop_and_resolver_is_idempotent():
    payload = {
        "experiences": [experience(start_date="2021", end_date="2024")],
        "certificates": [certificate(issue_date="2022", expiration_date="2025")],
    }
    first = reconcile_source_grounded_dates("Unrelated source", payload)
    second = reconcile_source_grounded_dates("Unrelated source", first.payload)
    assert first.payload == payload == second.payload
    assert first.audit == second.audit == ()


def test_only_approved_date_fields_change_and_audit_contains_no_source_values():
    payload = {"experiences": [experience(start_date="2024", end_date="2021")],
               "certificates": [certificate(issue_date="2025", expiration_date="2022",
                                                credential_url="https://example.test/credential")]}
    before = copy.deepcopy(payload)
    result, _ = resolve(
        "2021 to 2024 Engineer Acme Build APIs\n"
        "Cloud Certificate Issuer issued 2022 expires 2025",
        payload,
    )
    assert result.payload["experiences"][0]["company_name"] == before["experiences"][0]["company_name"]
    assert result.payload["experiences"][0]["description"] == before["experiences"][0]["description"]
    assert result.payload["certificates"][0]["name"] == before["certificates"][0]["name"]
    assert result.payload["certificates"][0]["credential_url"] == before["certificates"][0]["credential_url"]
    audit_text = json.dumps(result.audit)
    assert "Acme" not in audit_text and "Cloud Certificate" not in audit_text


class SequenceProvider:
    def __init__(self, payload):
        self.payload = CVExtractionProviderResponse.model_validate(payload)
        self.calls = 0

    async def generate_structured(self, **kwargs):
        self.calls += 1
        return self.payload


def test_service_resolves_before_canonical_validation_without_model_repair():
    provider = SequenceProvider({"experiences": [experience(start_date="2024", end_date="2021")]})
    service = CVStructuredExtractionService(provider=provider)
    result = asyncio.run(service.extract_from_text("2021 to 2024 Engineer Acme Build APIs"))
    assert result.experiences[0].start_date.year == 2021
    assert provider.calls == 1 and service.schema_retries == 0 and service.generation_attempts == 1
    assert service.last_diagnostics.date_resolution["status"] == "resolved"


def test_service_ambiguous_source_fails_typed_without_second_model_call(caplog):
    provider = SequenceProvider({"experiences": [experience(start_date="2024", end_date="2021")]})
    service = CVStructuredExtractionService(provider=provider)
    source = "2020 to 2022 Engineer Acme Build APIs 2021 to 2023 Engineer Acme Build APIs"
    with pytest.raises(CVExtractionCorrectionError):
        asyncio.run(service.extract_from_text(source))
    assert provider.calls == 1 and service.schema_retries == 0
    assert service.last_diagnostics.terminal_stage == "source_date_resolution_ms"
    assert service.last_diagnostics.date_resolution["reason"] == SOURCE_DATE_AMBIGUOUS
    assert "Acme" not in caplog.text and source not in caplog.text


def test_handled_token_fallback_does_not_mask_later_schema_terminal_stage():
    class Counter:
        async def count(self, payload):
            raise AITokenAccountingUnavailableError("synthetic")

        async def verify_safe_runtime(self):
            return None

    async def handler(request):
        content = {"experiences": [experience(start_date="2021", end_date="2024")],
                   "languages": "invalid"}
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
            "message": {"content": json.dumps(content)}, "prompt_eval_count": 100,
            "eval_count": 20})

    provider = OllamaProvider(base_url="http://mock.invalid", model="qwen3:8b",
        max_retries=0, token_counter=Counter(), transport=httpx.MockTransport(handler))
    service = CVStructuredExtractionService(provider=provider, max_schema_retries=0)
    with pytest.raises(Exception):
        asyncio.run(service.extract_from_text("2021 to 2024 Engineer Acme Build APIs"))
    assert service.last_diagnostics.terminal_stage == "schema_validate_1_ms"
