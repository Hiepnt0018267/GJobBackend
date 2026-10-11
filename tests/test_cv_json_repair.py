import copy
import json

import pytest
from pydantic import ValidationError

from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_json_repair import candidates, apply_patches, build_repair_prompt, RepairRejected


def invalid():
    return {'skills': [{'name': 'Python', 'level': 'advanced'}],
            'experiences': [{'company_name': 'C', 'position': 'R', 'description': ['Existing factual text']}],
            'projects': [{'name': 'P', 'technologies': 'Python'}]}


def allowed_for(payload):
    with pytest.raises(ValidationError) as error:
        StructuredCVExtractionResult.model_validate(payload)
    return candidates(payload, error.value), error.value


def response_for(allowed):
    return {'repairs': [{'path': list(path), 'value': value} for path, value in allowed.items()]}


def test_single_enum_patch_preserves_facts_and_original():
    payload = {'skills': [{'name': 'Python', 'level': 'advanced'}]}
    original = copy.deepcopy(payload)
    allowed, _ = allowed_for(payload)
    result = apply_patches(payload, response_for(allowed), allowed)
    assert StructuredCVExtractionResult.model_validate(result).skills[0].level.value == 'ADVANCED'
    assert payload == original
    assert result['skills'][0]['name'] == 'Python'


def test_multiple_leaf_paths_normalize_representation_only():
    payload = invalid()
    original = copy.deepcopy(payload)
    allowed, _ = allowed_for(payload)
    result = StructuredCVExtractionResult.model_validate(apply_patches(payload, response_for(allowed), allowed))
    assert result.experiences[0].description == 'Existing factual text'
    assert result.projects[0].technologies == ['Python']
    assert payload == original
    assert len(allowed) == 3


@pytest.mark.parametrize('path', [
    ['personal_info', 'full_name'], ['skills', 99, 'level'], ['skills', -1, 'level'],
    ['skills', True, 'level'], ['skills', '0', 'level'], ['skills', 0], [],
    ['skills', 0, '__class__'], ['../../skills', 0, 'level'], ['skills', 0, 'unknown'],
])
def test_unauthorized_unknown_root_parent_and_traversal_paths_rejected(path):
    payload = {'skills': [{'name': 'Python', 'level': 'advanced'}]}
    allowed, _ = allowed_for(payload)
    with pytest.raises((RepairRejected, ValidationError)):
        apply_patches(payload, {'repairs': [{'path': path, 'value': 'ADVANCED'}]}, allowed)


def test_duplicate_conflicting_patches_rejected():
    payload = {'skills': [{'name': 'Python', 'level': 'advanced'}]}
    allowed, _ = allowed_for(payload)
    response = response_for(allowed)
    response['repairs'].append({'path': ['skills', 0, 'level'], 'value': 'EXPERT'})
    with pytest.raises(RepairRejected):
        apply_patches(payload, response, allowed)


def test_new_factual_value_rejected_even_when_schema_valid():
    payload = {'experiences': [{'company_name': ['Existing C'], 'position': 'R'}]}
    allowed, _ = allowed_for(payload)
    response = {'repairs': [{'path': ['experiences', 0, 'company_name'], 'value': 'Invented C'}]}
    with pytest.raises(RepairRejected):
        apply_patches(payload, response, allowed)


@pytest.mark.parametrize('payload', [
    {'experiences': [{'position': 'R'}]},
    {'experiences': [{'company_name': 'C', 'position': 'R', 'start_date': '2024', 'end_date': '2020'}]},
    {'experiences': [{'company_name': 'C', 'position': 'R', 'start_date': 'unknown'}]},
    {'skills': [{'name': 'Python', 'level': 'good'}]},
    {'skills': {}},
    {'skills': [{'name': ['X' * 65]}]},
    {'skills': [{'name': ['X\nY']}]},
])
def test_missing_facts_dates_unknown_enum_and_large_values_fail_without_invention(payload):
    with pytest.raises(RepairRejected):
        allowed_for(payload)


def test_more_than_four_paths_rejected():
    payload = {'skills': [{'name': 'Python', 'level': 'advanced'} for _ in range(5)]}
    with pytest.raises(RepairRejected):
        allowed_for(payload)


def test_final_whole_object_validation_remains_authoritative():
    payload = {'skills': [{'name': 'Python', 'level': 'advanced'}]}
    allowed, _ = allowed_for(payload)
    # Whole-object validation rejects an independently invalid field; patch scope
    # must not expand to erase it. Orchestration must use this final schema.
    payload['experiences'] = [{'position': 'R'}]
    repaired = apply_patches(payload, response_for(allowed), allowed)
    with pytest.raises(ValidationError):
        StructuredCVExtractionResult.model_validate(repaired)


def test_prompt_has_previous_payload_but_not_cv_and_no_implicit_logging(caplog):
    payload = invalid()
    allowed, error = allowed_for(payload)
    summary = [{'path': list(item['loc']), 'type': item['type']}
               for item in error.errors(include_input=False, include_context=False, include_url=False)]
    prompt = build_repair_prompt(payload, summary, allowed)
    assert 'previous_object' in prompt and 'allowed_repairs' in prompt
    assert 'Do not add facts' in prompt
    assert not caplog.text
    assert len(json.dumps(response_for(allowed), ensure_ascii=False, separators=(',', ':')).encode()) <= 768


def test_patch_nested_unexpected_keys_and_missing_patches_rejected():
    payload = {'skills': [{'name': 'Python', 'level': 'advanced'}]}
    allowed, _ = allowed_for(payload)
    with pytest.raises(ValidationError):
        apply_patches(payload, {'repairs': [{'path': ['skills', 0, 'level'], 'value': {'unsafe': 'ADVANCED'}}]}, allowed)
    with pytest.raises(ValidationError):
        apply_patches(payload, {'repairs': []}, allowed)
