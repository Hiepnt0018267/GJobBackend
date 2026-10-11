"""Synthetic identity/extraction contract tests; no live LLM/DB."""
import asyncio
import copy
import uuid
from types import SimpleNamespace

import pytest

from app.ai.cv_extraction_prompt import CV_EXTRACTION_SYSTEM_INSTRUCTION
from app.schemas.cv import CVPersonalInfo
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_structured_extraction_service import (
    CVStructuredExtractionService, CVExtractionValidationError,
)
from app.services.matching_input_mapper import build_cv_matching_input
from app.services.matching_text_privacy import find_cv_identity_overlaps
from evaluation import prepare_ranking_canonical as prep


def structured(name=None):
    return StructuredCVExtractionResult.model_validate({
        'personal_info': {'full_name': name, 'email': 'person@example.com',
                          'phone': '0912345678', 'address': 'Private home address',
                          'linkedin_url': 'https://linkedin.com/in/synthetic'},
        'career_objective': 'Senior Backend Engineer; 5 years building APIs.',
        'experiences': [{'company_name': 'Demo', 'position': 'Senior Backend Engineer',
                         'description': 'Python FastAPI'}],
        'skills': [{'name': 'Python'}, {'name': 'FastAPI'}],
        'educations': [{'school_name': 'Demo University'}],
        'projects': [{'name': 'API Project'}], 'certificates': [{'name': 'CCNA'}],
        'languages': [{'name': 'English'}],
    })


def canonical(result):
    return build_cv_matching_input(SimpleNamespace(id=uuid.UUID(int=10)), result)


def test_explicit_real_name_excluded_and_identity_perturbation_invariance():
    result = structured('Nguyen Van A')
    before = result.model_dump(mode='json')
    text = canonical(result).semantic_text
    assert 'Nguyen Van A' not in text
    assert 'Senior Backend Engineer' in text and 'Python' in text and 'FastAPI' in text
    assert find_cv_identity_overlaps(text, result.personal_info) == ()
    changed = result.model_copy(update={'personal_info': CVPersonalInfo(full_name='Different Person')})
    assert canonical(changed).semantic_text == text
    assert result.model_dump(mode='json') == before


@pytest.mark.parametrize('heading', ['Senior Backend Engineer', 'PROFILE', 'RESUME', 'CURRICULUM VITAE'])
def test_misclassified_heading_is_not_recovered_or_deleted(heading):
    result = structured(heading)
    assert canonical(result).semantic_text == canonical(structured()).semantic_text
    assert 'Senior Backend Engineer' in canonical(result).semantic_text
    # Audit describes collision, not proof the heading is a real identity.
    if heading == 'Senior Backend Engineer':
        assert find_cv_identity_overlaps(canonical(result).semantic_text, result.personal_info) == ('full_name',)


def test_identity_only_has_no_semantic_fallback():
    result = StructuredCVExtractionResult(personal_info=CVPersonalInfo(full_name='Senior Backend Engineer'))
    assert canonical(result).semantic_text == ''


def test_shared_audit_detects_artificial_identity_injection_without_redaction():
    info = CVPersonalInfo(full_name='Nguyen Van A', address='Private home address')
    text = 'Nguyen Van A develops Python APIs.'
    assert find_cv_identity_overlaps(text, info) == ('full_name',)
    assert text == 'Nguyen Van A develops Python APIs.'


class MockProvider:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    async def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


@pytest.mark.parametrize('source,name', [
    ('Nguyen Van A\nBackend Developer\nPython FastAPI', 'Nguyen Van A'),
    ('Senior Data Analyst\n5 years experience\nSQL Power BI', None),
    ('PROFILE\nPython developer', None),
    ('CURRICULUM VITAE\nPython developer', None),
    ('RESUME\nPython developer', None),
])
def test_shared_contract_with_deterministic_mock_and_major_sections(source, name):
    provider = MockProvider(structured(name).model_dump(mode='json'))
    result = asyncio.run(CVStructuredExtractionService(provider=provider).extract_from_text(source))
    assert result.personal_info.full_name == name
    assert all(getattr(result, key) for key in ['skills','experiences','educations','projects','certificates','languages'])
    instruction = provider.calls[0]['system_instruction']
    assert 'omit full_name' in instruction
    assert "A job title is not a person's name" in instruction
    assert 'Company Name' in instruction
    assert provider.calls[0]['temperature'] == 0
    assert 'Only the candidate' in CVPersonalInfo.model_json_schema()['properties']['full_name']['description']
    # Mock verifies wiring/schema, not proof an actual LLM always follows instructions.


def test_malformed_output_still_rejected():
    provider = MockProvider({'skills': 'wrong type'})
    with pytest.raises(CVExtractionValidationError):
        asyncio.run(CVStructuredExtractionService(provider=provider).extract_from_text('CV source'))


def test_checkpoint_upgrade_is_source_scoped_and_does_not_accept_old_success(tmp_path):
    source = {'ref': '2', 'text': 'CV source'}
    old = prep.envelope('cv','c1',source,{'Resume.csv':'hash'},{'version':'old'})
    mapped, minimal = prep.canonical_cv('c1', structured('Nguyen Van A'))
    old.update(status='SUCCEEDED', canonical_input=mapped.model_dump(mode='json'),
               structured_result=minimal.model_dump(mode='json'))
    old['canonical_sha256'] = prep.digest(old['canonical_input'])
    old['canonical_fingerprint'] = prep.fingerprint_cv(mapped)
    path = tmp_path/'cvs.jsonl'
    prep.atomic_json(path,[old],lines=True)
    expected={'c1':prep.envelope('cv','c1',source,{'Resume.csv':'hash'},{'version':'new'})}
    with pytest.raises(prep.EvaluationDataError, match='IDENTITY_MISMATCH'):
        prep.read_records(path,expected,'cv')
    assert prep.read_records(path,expected,'cv',invalidate_incompatible=True) == {}
    assert prep.read_records(path,{'c1':old},'cv')
    wrong=copy.deepcopy(expected); wrong['c1']['source_sha256']='other source'
    with pytest.raises(prep.EvaluationDataError, match='IDENTITY_MISMATCH'):
        prep.read_records(path,wrong,'cv',invalidate_incompatible=True)
    prep.atomic_json(path,[old,old],lines=True)
    with pytest.raises(prep.EvaluationDataError, match='DUPLICATE'):
        prep.read_records(path,expected,'cv',invalidate_incompatible=True)
