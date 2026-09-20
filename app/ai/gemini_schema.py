from typing import TypeAlias


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

# Gemini Developer API rejects these Pydantic JSON Schema keywords for this
# structured-output path; backend Pydantic validation still enforces them.
UNSUPPORTED_GEMINI_SCHEMA_KEYS = frozenset(
    {"additionalProperties", "maxItems"}
)


def sanitize_schema_for_gemini(schema: JSONValue) -> JSONValue:
    """Return a provider-compatible copy without weakening the domain model."""
    if isinstance(schema, dict):
        return {
            key: sanitize_schema_for_gemini(value)
            for key, value in schema.items()
            if key not in UNSUPPORTED_GEMINI_SCHEMA_KEYS
        }
    if isinstance(schema, list):
        return [sanitize_schema_for_gemini(value) for value in schema]
    return schema
