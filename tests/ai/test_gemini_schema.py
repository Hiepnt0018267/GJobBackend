import copy

from pydantic import ValidationError
import pytest

from app.ai.gemini_schema import sanitize_schema_for_gemini
from app.schemas.cv_extraction import StructuredCVExtractionResult


def _contains_key(value: object, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(
            _contains_key(item, target) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False


def test_sanitizer_removes_unsupported_keys_recursively_without_mutation() -> None:
    schema = {
        "type": "object",
        "required": ["experience"],
        "additionalProperties": False,
        "properties": {
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "details": [
                            {
                                "type": "object",
                                "additionalProperties": False,
                            }
                        ]
                    },
                },
            }
        },
    }
    original = copy.deepcopy(schema)

    sanitized = sanitize_schema_for_gemini(schema)

    assert not _contains_key(sanitized, "additionalProperties")
    assert sanitized["type"] == "object"
    assert sanitized["required"] == ["experience"]
    assert schema == original


@pytest.mark.parametrize("schema", [{}, [], None, "string", 1, True])
def test_sanitizer_handles_minimal_json_values(schema) -> None:
    assert sanitize_schema_for_gemini(schema) == schema


def test_actual_cv_schema_is_sanitized_but_domain_stays_strict() -> None:
    domain_schema = StructuredCVExtractionResult.model_json_schema()

    assert _contains_key(domain_schema, "additionalProperties")
    assert not _contains_key(
        sanitize_schema_for_gemini(domain_schema), "additionalProperties"
    )
    sanitized = sanitize_schema_for_gemini(domain_schema)
    assert not _contains_key(sanitized, "maxItems")
    assert _contains_key(sanitized, "default")
    assert _contains_key(sanitized, "maxLength")
    assert _contains_key(sanitized, "minLength")

    with pytest.raises(ValidationError):
        StructuredCVExtractionResult.model_validate(
            {"candidate_score": 99, "personal_info": {"gender": "private"}}
        )
