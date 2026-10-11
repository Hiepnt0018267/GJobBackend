"""Sparse provider wire contract for CV extraction.

The wire model may omit values that the canonical extraction model already
restores deterministically.  Canonical validation remains the final authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, create_model, model_validator

from app.schemas.cv import (
    CVCertificateItem,
    CVEducationItem,
    CVExperienceItem,
    CVLanguageItem,
    CVPersonalInfo,
    CVProjectItem,
    CVSkillItem,
)
from app.schemas.cv_extraction import StructuredCVExtractionResult


CV_EXTRACTION_WIRE_CONTRACT_VERSION = "cv-extraction-sparse-wire-v1"
_SCHEMA_METADATA_KEYS = frozenset({"default", "description", "examples", "title"})


def _wire_item(name: str, source: type[BaseModel], *, exclude: frozenset[str] = frozenset()):
    fields = {
        field_name: (field.annotation, deepcopy(field))
        for field_name, field in source.model_fields.items()
        if field_name not in exclude
    }
    return create_model(
        name,
        __config__=ConfigDict(extra="forbid"),
        __module__=__name__,
        **fields,
    )


CVPersonalInfoWire = _wire_item("CVPersonalInfoWire", CVPersonalInfo)
CVEducationItemWire = _wire_item("CVEducationItemWire", CVEducationItem)
CVExperienceItemWire = _wire_item(
    "CVExperienceItemWire",
    CVExperienceItem,
)
CVSkillItemWire = _wire_item("CVSkillItemWire", CVSkillItem)
CVProjectItemWire = _wire_item("CVProjectItemWire", CVProjectItem)
CVCertificateItemWire = _wire_item("CVCertificateItemWire", CVCertificateItem)
CVLanguageItemWire = _wire_item("CVLanguageItemWire", CVLanguageItem)


def _minimize_schema(value: Any, *, property_map: bool = False) -> Any:
    if isinstance(value, dict):
        return {
            key: _minimize_schema(item, property_map=key == "properties")
            for key, item in value.items()
            if property_map or key not in _SCHEMA_METADATA_KEYS
        }
    if isinstance(value, list):
        return [_minimize_schema(item) for item in value]
    return value


def _prune_unused_defs(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        return schema

    def referenced(value: Any) -> set[str]:
        if isinstance(value, dict):
            refs = {
                ref.rsplit("/", 1)[-1]
                for ref in (value.get("$ref"),)
                if isinstance(ref, str) and ref.startswith("#/$defs/")
            }
            for key, item in value.items():
                if key != "$defs":
                    refs.update(referenced(item))
            return refs
        if isinstance(value, list):
            result: set[str] = set()
            for item in value:
                result.update(referenced(item))
            return result
        return set()

    used = referenced(schema)
    pending = list(used)
    while pending:
        name = pending.pop()
        for dependency in referenced(defs.get(name)):
            if dependency not in used:
                used.add(dependency)
                pending.append(dependency)
    schema["$defs"] = {name: value for name, value in defs.items() if name in used}
    return schema


class CVExtractionProviderResponse(BaseModel):
    """Typed sparse JSON accepted from the AI provider."""

    model_config = ConfigDict(extra="forbid")

    personal_info: CVPersonalInfoWire = Field(default_factory=CVPersonalInfoWire)
    career_objective: str | None = Field(default=None, max_length=5000)
    educations: list[CVEducationItemWire] = Field(default_factory=list, max_length=100)
    experiences: list[CVExperienceItemWire] = Field(default_factory=list, max_length=100)
    skills: list[CVSkillItemWire] = Field(default_factory=list, max_length=100)
    projects: list[CVProjectItemWire] = Field(default_factory=list, max_length=100)
    certificates: list[CVCertificateItemWire] = Field(default_factory=list, max_length=100)
    languages: list[CVLanguageItemWire] = Field(default_factory=list, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def reject_internal_metadata(cls, value: object, info: ValidationInfo) -> object:
        if (info.context or {}).get("allow_verified_internal_metadata"):
            return value
        if isinstance(value, dict) and isinstance(value.get("experiences"), list):
            if any(
                isinstance(item, dict) and "date_consistency" in item
                for item in value["experiences"]
            ):
                raise ValueError("date_consistency is internal verified metadata")
        return value

    @classmethod
    def model_json_schema(cls, *args, **kwargs) -> dict[str, Any]:
        """Keep structural constraints while dropping provider-irrelevant metadata."""

        schema = _minimize_schema(super().model_json_schema(*args, **kwargs))
        experience = schema.get("$defs", {}).get("CVExperienceItemWire", {})
        experience.get("properties", {}).pop("date_consistency", None)
        if "required" in experience:
            experience["required"] = [
                name for name in experience["required"] if name != "date_consistency"
            ]
        return _prune_unused_defs(schema)


def sparse_provider_payload(value: StructuredCVExtractionResult) -> dict[str, Any]:
    """Serialize canonical data without absent/default wire values."""

    return value.model_dump(
        mode="json",
        exclude_none=True,
        exclude_defaults=True,
    )


def validate_and_normalize_provider_response(
    value: object,
) -> StructuredCVExtractionResult:
    """Validate sparse wire data, restore defaults, then revalidate canonically."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_unset=True)
    wire = CVExtractionProviderResponse.model_validate(value)
    return StructuredCVExtractionResult.model_validate(wire.model_dump(mode="json"))


def validate_reconciled_provider_response(
    value: dict[str, Any],
    *,
    validation_context: dict[str, Any],
) -> StructuredCVExtractionResult:
    """Canonical validation for an already wire-validated internal payload."""

    return StructuredCVExtractionResult.model_validate(
        value,
        context=validation_context,
    )


def normalize_sparse_canonical_artifact(
    value: object,
    *,
    validation_context: dict[str, Any],
) -> StructuredCVExtractionResult:
    """Round-trip a previously verified canonical artifact with internal proof."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_unset=True)
    wire = CVExtractionProviderResponse.model_validate(
        value,
        context={"allow_verified_internal_metadata": True},
    )
    return StructuredCVExtractionResult.model_validate(
        wire.model_dump(mode="json"),
        context=validation_context,
    )
