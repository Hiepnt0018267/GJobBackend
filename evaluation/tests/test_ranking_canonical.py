"""Synthetic production-contract preparation tests. No live provider or DB."""
import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from app.ai.ollama_provider import OllamaProvider
from app.ai.exceptions import AIProviderError
from app.services.cv_structured_extraction_service import CVStructuredExtractionService
from evaluation.common import EvaluationDataError
from evaluation import prepare_ranking_canonical as prep


PAYLOAD = {'personal_info': {'full_name': 'Synthetic Candidate', 'email': 'private@example.com',
                            'phone': '0900000000', 'address': 'Private Home Address',
                            'date_of_birth': '1990-01-01'},
           'skills': [{'name': ' Python '}, {'name': 'python'}],
           'experiences': [{'company_name': 'Demo Company', 'position': 'Developer',
                            'description': 'Built APIs.'}]}


class FakeProvider:
    last_metrics = None

    def __init__(self, payload=None, error=None):
        self.payload = PAYLOAD if payload is None else payload
        self.error = error
        self.calls = []

    async def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.payload


def test_sources_missing_wrong_reference_and_empty():
    entities = {'c1': {'ref': '2', 'text': 'CV source'}}
    assert prep.resolve('c1', '2', entities) == entities['c1']
    for cid, ref, data in [('missing', '2', entities), ('c1', '9', entities),
                           ('j1', '2', {'j1': {'ref': '2', 'text': ''}})]:
        with pytest.raises(EvaluationDataError):
            prep.resolve(cid, ref, data)
    assert prep.resolve('j1', '3', {'j1': {'ref': '3', 'text': 'JD'}})['text'] == 'JD'


def test_exact_cv_mapper_reuse_and_privacy(monkeypatch):
    actual = prep.mapper.build_cv_matching_input
    calls = []

    def observed(*args, **kwargs):
        result = actual(*args, **kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(prep.mapper, 'build_cv_matching_input', observed)
    canonical, minimized = prep.canonical_cv('c1', PAYLOAD)
    assert len(calls) == 2
    assert canonical.semantic_text == calls[0].semantic_text
    assert canonical.location is None
    assert calls[0].location is not None
    assert minimized.personal_info.full_name is None
    for value in ('Synthetic Candidate', 'private@example.com', '0900000000',
                  'Private Home Address', '1990-01-01'):
        assert value not in json.dumps(canonical.model_dump(mode='json'))
    assert len(canonical.skills) == 1


def test_sensitive_prose_rejected_not_rewritten():
    payload = copy.deepcopy(PAYLOAD)
    payload['career_objective'] = 'Contact private@example.com'
    canonical, _ = prep.canonical_cv('c1', payload)
    assert 'private@example.com' not in canonical.semantic_text
    with pytest.raises(EvaluationDataError, match='EMPTY'):
        prep.canonical_cv('c1', {})


def test_jd_exact_mapper_and_absence_policy(monkeypatch):
    actual = prep.mapper.build_job_matching_input
    calls = []

    def observed(job):
        calls.append(job)
        return actual(job)

    monkeypatch.setattr(prep.mapper, 'build_job_matching_input', observed)
    canonical = prep.canonical_jd('j1', {'title': ' Developer ', 'description': 'Build APIs', 'skills_desc': ''})
    assert len(calls) == 1
    assert canonical.semantic_text == actual(calls[0]).semantic_text
    assert canonical.requirements is None
    assert canonical.skills == []
    assert canonical.level is None
    with pytest.raises(EvaluationDataError):
        prep.canonical_jd('j1', {'title': '', 'description': 'JD'})
    with pytest.raises(EvaluationDataError, match='SKILL_MAPPING'):
        prep.canonical_jd('j1', {'title': 'Job', 'description': 'JD', 'skills_desc': 'arbitrary prose'})


def test_jd_contact_uses_shared_production_sanitizer_without_source_mutation():
    raw = {'title': 'Developer', 'description': 'Build APIs. Apply to contact@example.com'}
    canonical = prep.canonical_jd('j1', raw)
    assert 'contact@example.com' not in canonical.semantic_text
    assert '[CONTACT]' in canonical.semantic_text
    assert raw['description'].endswith('contact@example.com')


def test_jd_preflight_happens_before_provider_construction():
    source = prep.Path(prep.__file__).read_text(encoding='utf-8')
    guard = source.index("if any(record['status'] != 'SUCCEEDED' for record in jd_records.values())")
    provider = source.index('provider = create_ai_provider()')
    assert guard < provider
    assert 'return' in source[guard:provider]


def run_fake(tmp_path, provider, *, existing=None, labels=None):
    path = tmp_path/'cvs.jsonl'
    source = {'c1': {'ref': '2', 'text': 'CV-only Python developer'}}
    expected = {'c1': prep.envelope('cv', 'c1', source['c1'], {'Resume.csv': 'hash'}, {'model': 'fake'})}
    records = asyncio.run(prep.prepare_cvs(expected, source, existing or {},
                          CVStructuredExtractionService(provider=provider), path))
    return records, expected, path


def test_extraction_only_cv_prompt_no_label_dependence(tmp_path):
    first = FakeProvider()
    second = FakeProvider()
    a, _, _ = run_fake(tmp_path, first, labels={'grade': '0', 'reason': 'Bad'})
    b, _, _ = run_fake(tmp_path, second, labels={'grade': '2', 'reason': 'Good'})
    assert a['c1']['canonical_input'] == b['c1']['canonical_input']
    assert first.calls == second.calls
    assert 'CV-only Python developer' in first.calls[0]['prompt']
    assert 'ranking_case' not in first.calls[0]['prompt']
    assert first.calls[0]['temperature'] == 0


def test_resume_reuses_success_and_detects_hash_change(tmp_path):
    provider = FakeProvider()
    records, expected, path = run_fake(tmp_path, provider)
    loaded = prep.read_records(path, expected, 'cv')
    second = FakeProvider(error=AssertionError('must not call'))
    again, _, _ = run_fake(tmp_path, second, existing=loaded)
    assert second.calls == []
    assert again == records
    corrupted = copy.deepcopy(expected)
    corrupted['c1']['source_sha256'] = 'changed'
    with pytest.raises(EvaluationDataError, match='IDENTITY'):
        prep.read_records(path, corrupted, 'cv')


@pytest.mark.parametrize('payload,error,code', [
    ({'skills': 'Python'}, None, 'SCHEMA_VALIDATION_FAILED'),
    (None, AIProviderError('safe error'), 'PROVIDER_UNAVAILABLE'),
])
def test_controlled_failure_checkpoint(tmp_path, payload, error, code):
    records, _, path = run_fake(tmp_path, FakeProvider(payload=payload, error=error))
    assert records['c1']['status'] == 'FAILED'
    assert records['c1']['error_code'] == code
    assert 'canonical_input' not in records['c1']
    assert 'safe error' not in path.read_text(encoding='utf-8')


def test_production_ollama_invalid_json_controlled(tmp_path):
    from app.ai.ollama_token_budget import PromptAccounting
    class Counter:
        async def count(self, payload): return PromptAccounting(100, 0, 8192)
    provider = OllamaProvider(base_url='http://mock.invalid', model='qwen3:8b',
        token_counter=Counter(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200,
            json={'done': True, 'done_reason': 'stop', 'message': {'content': 'invalid JSON'}})))
    records, _, _ = run_fake(tmp_path, provider)
    assert records['c1']['error_code'] == 'SCHEMA_VALIDATION_FAILED'


def test_manifest_100_rows_and_partial_readiness():
    identities = [{'ranking_case_id': f'case{i//10}', 'pair_id': f'p{i}',
                   'cv_id': f'c{i}', 'job_id': f'j{i//10}'} for i in range(100)]
    cvs = {f'c{i}': {'status': 'SUCCEEDED'} for i in range(99)}
    jds = {f'j{i}': {'status': 'SUCCEEDED'} for i in range(10)}
    rows = prep.pair_manifest(identities, cvs, jds, prep.Path('cvs.jsonl'), prep.Path('jds.jsonl'))
    assert len(rows) == 100
    assert sum(r['ready_for_scoring'] == 'true' for r in rows) == 99
    assert all(r['canonical_cv_ref'] and r['canonical_jd_ref'] for r in rows)
    with pytest.raises(EvaluationDataError, match='DUPLICATE'):
        prep.pair_manifest(identities + identities[:1], cvs, jds, prep.Path('cvs'), prep.Path('jds'))


def test_no_semantic_import_or_ground_truth_writer():
    source = prep.Path(prep.__file__).read_text(encoding='utf-8')
    assert 'from app.embeddings' not in source
    assert 'import semantic_matching' not in source
    assert 'atomic_csv(args.input' not in source
