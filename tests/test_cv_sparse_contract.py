from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.cv_extraction_wire import (
    CVExtractionProviderResponse,
    normalize_sparse_canonical_artifact,
    sparse_provider_payload,
    validate_and_normalize_provider_response,
)
from app.services.cv_source_consistency import validate_source_grounded


def canonical(payload=None):
    return StructuredCVExtractionResult.model_validate(payload or {})


def round_trip(value):
    sparse = sparse_provider_payload(value)
    return sparse, validate_and_normalize_provider_response(sparse)


def test_optional_null_empty_list_and_nested_defaults_are_omitted():
    value = canonical({"career_objective": None, "skills": []})
    sparse, restored = round_trip(value)

    assert sparse == {}
    assert restored.model_dump(mode="json") == value.model_dump(mode="json")


def test_populated_values_and_repeated_item_counts_are_preserved():
    value = canonical(
        {
            "personal_info": {"full_name": "Candidate"},
            "career_objective": "Build reliable systems",
            "experiences": [
                {"company_name": "A", "position": "Engineer"},
                {"company_name": "B", "position": "Lead", "is_current": True},
            ],
            "educations": [{"school_name": "University"}],
            "skills": [{"name": "Python"}, {"name": "FastAPI"}],
            "projects": [{"name": "Project", "technologies": ["Python"]}],
        }
    )
    sparse, restored = round_trip(value)

    assert len(sparse["experiences"]) == len(restored.experiences) == 2
    assert len(sparse["skills"]) == len(restored.skills) == 2
    assert len(sparse["projects"]) == len(restored.projects) == 1
    assert sparse["experiences"][0] == {
        "company_name": "A",
        "position": "Engineer",
    }
    assert restored.model_dump(mode="json") == value.model_dump(mode="json")


def test_required_factual_field_cannot_be_omitted_or_invented():
    with pytest.raises(ValidationError):
        validate_and_normalize_provider_response(
            {"experiences": [{"position": "Engineer"}]}
        )


def test_optional_empty_string_normalizes_to_omission():
    value = canonical({"career_objective": "   "})
    sparse, restored = round_trip(value)

    assert "career_objective" not in sparse
    assert restored.career_objective is None


def test_partial_date_precision_round_trips_without_null_subfields():
    value = canonical(
        {
            "experiences": [
                {
                    "company_name": "A",
                    "position": "Engineer",
                    "start_date": {"year": 2022, "precision": "year"},
                    "end_date": {
                        "year": 2024,
                        "month": 3,
                        "precision": "month",
                    },
                }
            ]
        }
    )
    sparse, restored = round_trip(value)

    assert sparse["experiences"][0]["start_date"] == {
        "year": 2022,
        "precision": "year",
    }
    assert restored.model_dump(mode="json") == value.model_dump(mode="json")


def test_wire_schema_is_minified_but_keeps_constraints_and_forbids_internal_metadata():
    schema = CVExtractionProviderResponse.model_json_schema()

    def assert_no_schema_metadata(value, *, property_map=False):
        if isinstance(value, dict):
            if not property_map:
                assert not ({"title", "description", "default", "examples"} & value.keys())
            for key, item in value.items():
                assert_no_schema_metadata(item, property_map=key == "properties")
        elif isinstance(value, list):
            for item in value:
                assert_no_schema_metadata(item)

    assert_no_schema_metadata(schema)
    assert schema["additionalProperties"] is False
    experience = schema["$defs"]["CVExperienceItemWire"]
    assert experience["required"] == ["company_name", "position"]
    assert "date_consistency" not in experience["properties"]
    assert "SourceDateConsistency" not in schema["$defs"]
    assert experience["properties"]["description"]["anyOf"][0]["maxLength"] == 10000


def test_wire_rejects_extra_fields_and_does_not_change_canonical_schema():
    canonical_schema = deepcopy(StructuredCVExtractionResult.model_json_schema())

    with pytest.raises(ValidationError):
        CVExtractionProviderResponse.model_validate({"candidate_score": 99})

    assert StructuredCVExtractionResult.model_json_schema() == canonical_schema


def test_verified_internal_metadata_round_trips_only_through_artifact_path():
    value, _, _, context = validate_source_grounded(
        "Experience May 2023 to March 2023 Developer ABC Build APIs",
        {
            "experiences": [{
                "company_name": "ABC",
                "position": "Developer",
                "description": "Build APIs",
                "start_date": "May 2023",
                "end_date": "March 2023",
            }],
        },
    )
    sparse = sparse_provider_payload(value)

    with pytest.raises(ValidationError):
        validate_and_normalize_provider_response(sparse)

    restored = normalize_sparse_canonical_artifact(
        sparse,
        validation_context=context,
    )
    assert restored.model_dump(mode="json") == value.model_dump(mode="json")
