import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.ai.extraction_diagnostics import CURRENT, ExtractionDiagnostics, STAGES, safe_validation_errors
from app.ai.ollama_provider import OllamaProvider
from app.ai.ollama_token_budget import PromptAccounting
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_structured_extraction_service import (
    CVStructuredExtractionService, CVExtractionCorrectionError, CVExtractionDeadlineError,
)


VALID = {'personal_info': {'full_name': 'Synthetic'}, 'educations': [],
         'experiences': [], 'skills': [], 'projects': [], 'certificates': [], 'languages': []}


class Counter:
    async def count(self, payload):
        return PromptAccounting(100, 0, 10240)


def provider_for(responses):
    index = [0]
    async def handler(request):
        value = responses[index[0]]
        index[0] += 1
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
            'message': {'content': json.dumps(value)}, 'prompt_eval_count': 100,
            'eval_count': 20, 'prompt_eval_duration': 1000000,
            'eval_duration': 2000000, 'total_duration': 3000000})
    return OllamaProvider(base_url='http://mock.invalid', model='qwen3:8b',
        transport=httpx.MockTransport(handler), token_counter=Counter(), max_retries=0)


def test_stages_metadata_and_not_run_are_safe(caplog):
    caplog.set_level('INFO')
    service = CVStructuredExtractionService(provider=provider_for([VALID]))
    asyncio.run(service.extract_from_text('SECRET_SOURCE_DO_NOT_LOG'))
    d = service.last_diagnostics.snapshot()
    for name in ('prompt_build_ms', 'token_count_ms', 'preflight_ms',
                 'provider_call_1_ms', 'json_parse_1_ms', 'schema_validate_1_ms', 'total_operation_ms'):
        assert d['timings'][name] >= 0
    for name in ('document_parse_ms', 'provider_call_2_ms', 'correction_build_ms', 'persistence_ms'):
        assert d['timings'][name] is None
    assert set(d['timings']) == set(STAGES)
    assert d['calls'][0]['eval_duration_ns'] == 2000000
    assert d['calls'][0]['prompt_eval_duration_ns'] == 1000000
    assert d['calls'][0]['done'] is True
    assert CURRENT.get() is None
    assert 'SECRET_SOURCE_DO_NOT_LOG' not in caplog.text
    assert 'Synthetic' not in caplog.text


def test_initial_and_correction_errors_are_distinct(caplog,monkeypatch):
    caplog.set_level('WARNING')
    first = dict(VALID, skills=[{'name':'Python','level':'advanced'}],experiences=[{'company_name':'C','position':'R','description':['SECRET_VALUE']}])
    second = {'repairs':[{'path':['skills',0,'level'],'value':'ADVANCED'},{'path':['experiences',0,'description'],'value':'SECRET_VALUE'}]}
    import app.services.cv_patch_repair_service as repair_module
    original = repair_module.apply_patches
    def modified(*args):
        result=original(*args);result['languages']='SECRET_VALUE';return result
    monkeypatch.setattr(repair_module,'apply_patches',modified)
    service = CVStructuredExtractionService(provider=provider_for([first]),repair_provider=provider_for([second]))
    with pytest.raises(CVExtractionCorrectionError):
        asyncio.run(service.extract_from_text('SECRET_SOURCE'))
    d = service.last_diagnostics.snapshot()
    assert d['validation']['1']['error_count'] == 2
    assert d['validation']['2']['error_count'] == 1
    assert {tuple(e['path']) for e in d['validation']['1']['errors']} == {('skills',0,'level'), ('experiences',0,'description')}
    assert d['validation']['2']['errors'] == [{'path': ['languages'], 'type': 'list_type'}]
    assert d['correction'] == 'patch_repair'
    assert d['terminal_stage'] == 'schema_validate_2_ms'
    assert 'SECRET_' not in caplog.text
    assert 'input' not in json.dumps(d['validation'])
    assert 'CV extraction diagnostics=' in caplog.text


def test_unknown_extra_key_and_error_context_are_not_logged():
    class Strict(BaseModel):
        model_config = ConfigDict(extra='forbid')
        count: int
    with pytest.raises(ValidationError) as caught:
        Strict.model_validate({'count': 'SECRET_VALUE', 'SECRET_KEY': 'SECRET_VALUE'})
    d = safe_validation_errors(caught.value, Strict)
    assert {'path': ['unknown'], 'type': 'extra_forbidden'} in d['errors']
    assert 'SECRET' not in json.dumps(d)
    assert 'msg' not in json.dumps(d)


def test_correction_blocked_typed_deadline_with_initial_errors(monkeypatch):
    clock = [0.0]
    import app.services.cv_structured_extraction_service as svc
    monkeypatch.setattr(svc.time, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(svc.settings, 'cv_extraction_total_timeout_seconds', 150.0)
    monkeypatch.setattr(svc.settings, 'cv_extraction_correction_min_seconds', 60.0)
    class Fake:
        calls = 0
        async def generate_structured(self, **kwargs):
            self.calls += 1
            clock[0] = 110.0
            return dict(VALID, skills=[{'name':'Python','level':'advanced'}])
    fake = Fake()
    service = CVStructuredExtractionService(provider=fake)
    with pytest.raises(CVExtractionDeadlineError, match='Insufficient'):
        asyncio.run(service.extract_from_text('Synthetic'))
    assert fake.calls == 1
    assert service.last_diagnostics.correction == 'blocked_insufficient_budget'
    assert service.last_diagnostics.timings['provider_call_2_ms'] is None
    assert service.last_diagnostics.validation['1']['errors'][0]['path'] == ['skills',0,'level']


@pytest.mark.parametrize('remaining', [15, 60, 150])
def test_provider_timeout_is_capped_by_remaining_budget(remaining, monkeypatch):
    d = ExtractionDiagnostics(remaining, clock=lambda: 0.0)
    monkeypatch.setattr('app.ai.ollama_provider.time.perf_counter', lambda: 0.0)
    seen = []
    p = provider_for([VALID])
    async def handler(request):
        seen.append(request.extensions['timeout']['read'])
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
            'message': {'content': json.dumps(VALID)}, 'prompt_eval_count': 100, 'eval_count': 20})
    p._transport = httpx.MockTransport(handler)
    async def run():
        token = CURRENT.set(d)
        try:
            return await p.generate_structured('Synthetic', StructuredCVExtractionResult)
        finally:
            CURRENT.reset(token)
    asyncio.run(run())
    assert seen == [min(90, remaining)]
    assert d.calls[0]['effective_provider_timeout_ms'] <= d.calls[0]['remaining_operation_budget_before_call_ms']


def test_cancellation_retains_partial_stage_timing():
    d = ExtractionDiagnostics(150, clock=lambda: 10.0)
    with pytest.raises(asyncio.CancelledError):
        with d.stage('provider_call_1_ms'):
            raise asyncio.CancelledError()
    assert d.timings['provider_call_1_ms'] == 0
    assert d.terminal_stage == 'provider_call_1_ms'


def test_parallel_operations_do_not_share_diagnostics():
    async def run():
        services = [CVStructuredExtractionService(provider=provider_for([VALID])) for _ in range(2)]
        await asyncio.gather(*(s.extract_from_text('Synthetic') for s in services))
        assert services[0].last_diagnostics is not services[1].last_diagnostics
        assert all(len(s.last_diagnostics.calls) == 1 for s in services)
    asyncio.run(run())


def test_document_parse_timer_and_persistence_are_separate(monkeypatch, caplog):
    from types import SimpleNamespace
    from app.services.cv_extraction_service import CandidateCVExtractionService
    class Reader:
        def extract_uploaded_cv(self, source):
            return SimpleNamespace(text='SECRET_DOCUMENT')
    async def thread_without_sleep(fn, *args):
        return fn(*args)
    monkeypatch.setattr(asyncio, 'to_thread', thread_without_sleep)
    service = CVStructuredExtractionService(provider=provider_for([VALID]), text_extraction_service=Reader())
    asyncio.run(service.extract_uploaded_cv(object()))
    assert service.last_diagnostics.timings['document_parse_ms'] >= 0
    candidate = CandidateCVExtractionService.__new__(CandidateCVExtractionService)
    candidate._diagnostic_extractor = service
    caplog.set_level('INFO')
    with candidate._persistence_diagnostics('synthetic-id'):
        pass
    assert service.last_diagnostics.timings['persistence_ms'] >= 0
    assert 'synthetic-id' in caplog.text
    assert 'SECRET_DOCUMENT' not in caplog.text


def test_schema_path_code_has_no_raw_input_or_context():
    class Required(BaseModel):
        full_name: str
    with pytest.raises(ValidationError) as caught:
        Required.model_validate({})
    summary = safe_validation_errors(caught.value, Required)
    assert {'path': ['full_name'], 'type': 'missing'} in summary['errors']
    assert set(summary['errors'][0]) == {'path', 'type'}


def test_existing_transport_retry_does_not_reset_remaining_budget(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.ai.ollama_provider.time.perf_counter', lambda: clock[0])
    d = ExtractionDiagnostics(60, clock=lambda: clock[0])
    seen = []
    p = provider_for([VALID])
    p._max_retries = 1
    p._retry_delay_seconds = 0
    async def handler(request):
        seen.append(request.extensions['timeout']['read'])
        if len(seen) == 1:
            clock[0] = 40.0
            raise httpx.ConnectError('Synthetic', request=request)
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
            'message': {'content': json.dumps(VALID)}, 'prompt_eval_count': 100, 'eval_count': 20})
    p._transport = httpx.MockTransport(handler)
    async def run():
        token = CURRENT.set(d)
        try:
            await p.generate_structured('Synthetic', StructuredCVExtractionResult)
        finally:
            CURRENT.reset(token)
    asyncio.run(run())
    assert seen == [60, 20]
    assert d.calls[0]['transport_attempts'] == 2
