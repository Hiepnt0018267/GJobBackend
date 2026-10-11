import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest
from app.ai.exceptions import (AITimeoutError, AIContextBudgetExceededError, AIJSONParseError,
    AIProviderError, AIOutputBudgetExceededError)
from app.ai.ollama_provider import OllamaProvider
from app.ai.ollama_token_budget import PromptAccounting
from app.ai.cv_extraction_prompt import build_cv_extraction_prompt, CV_EXTRACTION_SYSTEM_INSTRUCTION
from app.services.cv_structured_extraction_service import (
    CVStructuredExtractionService, CVExtractionCorrectionError, CVExtractionDeadlineError,
    CVAIProviderTimeoutError, CVAIContextBudgetError, CVExtractionJSONError, CVAIProviderUnavailableError)
from app.services.cv_patch_repair_service import create_repair_provider, ExactRepairCounter

BAD = {'skills': [{'name': 'Python', 'level': 'advanced'}]}
PATCH = {'repairs': [{'path': ['skills', 0, 'level'], 'value': 'ADVANCED'}]}


class Sequence:
    def __init__(self, *values): self.values = iter(values); self.calls = []
    async def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        value = next(self.values)
        if isinstance(value, BaseException): raise value
        return copy.deepcopy(value)


def test_primary_success_exact_prompt_schema_and_no_repair():
    from app.schemas.cv_extraction import StructuredCVExtractionResult
    from app.schemas.cv_extraction_wire import CVExtractionProviderResponse
    primary = Sequence({'skills': [{'name': 'Python'}]}); repair = Sequence()
    result = asyncio.run(CVStructuredExtractionService(primary, repair_provider=repair).extract_from_text('  CV ONLY  '))
    assert primary.calls == [dict(prompt=build_cv_extraction_prompt('CV ONLY'),
        response_schema=CVExtractionProviderResponse, system_instruction=CV_EXTRACTION_SYSTEM_INSTRUCTION, temperature=0.0)]
    assert result.model_dump(mode='json') == StructuredCVExtractionResult.model_validate({'skills': [{'name': 'Python'}]}).model_dump(mode='json')
    assert not repair.calls


def test_one_repair_no_cv_facts_changed_and_diagnostics(caplog):
    primary = Sequence(BAD); repair = Sequence(PATCH)
    service = CVStructuredExtractionService(primary, repair_provider=repair)
    result = asyncio.run(service.extract_from_text('SECRET_CV_SOURCE'))
    assert len(primary.calls) == len(repair.calls) == 1
    assert 'SECRET_CV_SOURCE' not in repair.calls[0]['prompt']
    assert result.skills[0].level.value == 'ADVANCED' and result.skills[0].name == 'Python'
    assert service.last_diagnostics.repair['validation_success'] is True
    assert service.last_diagnostics.repair['patch_count'] == 1
    assert 'SECRET_CV_SOURCE' not in caplog.text and 'ADVANCED' not in caplog.text


@pytest.mark.parametrize('patch', [{}, {'repairs': []}, {'repairs': [{'path': ['personal_info', 'full_name'], 'value': 'invented'}]},
    {'repairs': [{'path': ['skills', 0, 'level'], 'value': 'EXPERT'}]}])
def test_bad_patch_terminates_no_retry(patch):
    primary = Sequence(BAD); repair = Sequence(patch)
    with pytest.raises(CVExtractionCorrectionError):
        asyncio.run(CVStructuredExtractionService(primary, repair_provider=repair).extract_from_text('CV'))
    assert len(primary.calls) == len(repair.calls) == 1


@pytest.mark.parametrize('error,expected', [(AITimeoutError('safe'), CVAIProviderTimeoutError),
    (AIContextBudgetExceededError('safe'), CVAIContextBudgetError), (AIJSONParseError('safe'), CVExtractionJSONError),
    (AIProviderError('safe'), CVAIProviderUnavailableError)])
def test_non_schema_primary_never_repairs(error, expected):
    repair = Sequence()
    with pytest.raises(expected):
        asyncio.run(CVStructuredExtractionService(Sequence(error), repair_provider=repair).extract_from_text('CV'))
    assert not repair.calls


@pytest.mark.parametrize('error,reason', [(AITimeoutError('safe'), 'repair_provider_timeout'),
    (AIContextBudgetExceededError('safe'), 'repair_context_budget_exceeded'),
    (AIOutputBudgetExceededError('safe'), 'repair_output_budget_exhausted')])
def test_repair_failure_typed_and_one_attempt(error, reason):
    repair = Sequence(error); service = CVStructuredExtractionService(Sequence(BAD), repair_provider=repair)
    with pytest.raises(CVExtractionCorrectionError): asyncio.run(service.extract_from_text('CV'))
    assert len(repair.calls) == 1 and service.last_diagnostics.repair['reason'] == reason


def test_remaining_budget_blocks_repair(monkeypatch):
    import app.services.cv_structured_extraction_service as module
    clock = [0.0]; monkeypatch.setattr(module.time, 'perf_counter', lambda: clock[0])
    class SlowPrimary(Sequence):
        async def generate_structured(self, **kwargs): clock[0] = 180.0; return BAD
    repair = Sequence(); service = CVStructuredExtractionService(SlowPrimary(), repair_provider=repair)
    with pytest.raises(CVExtractionDeadlineError): asyncio.run(service.extract_from_text('CV'))
    assert not repair.calls and service.last_diagnostics.terminal_stage == 'repair_admission'


def test_final_schema_invalid_is_terminal(monkeypatch):
    import app.services.cv_patch_repair_service as module
    original = module.apply_patches
    def changed(*args):
        result = original(*args); result['experiences'] = [{'position': 'R'}]; return result
    monkeypatch.setattr(module, 'apply_patches', changed)
    repair = Sequence(PATCH); service = CVStructuredExtractionService(Sequence(BAD), repair_provider=repair)
    with pytest.raises(CVExtractionCorrectionError): asyncio.run(service.extract_from_text('CV'))
    assert len(repair.calls) == 1 and service.last_diagnostics.repair['reason'] == 'final_schema_invalid'
    assert service.last_diagnostics.validation['2']['error_count'] == 1


def test_real_provider_context_guard_and_patch_budget_without_live_request():
    class Counter:
        async def count(self, payload):
            assert payload['options']['num_predict'] == 1024
            return PromptAccounting(9000, 0, 10240)
    calls = []
    provider = OllamaProvider(base_url='http://mock.invalid', model='qwen3:8b', num_predict=1024,
        timeout_seconds=40, max_retries=0, token_counter=Counter(), transport=httpx.MockTransport(lambda r: calls.append(r)))
    service = CVStructuredExtractionService(Sequence(BAD), repair_provider=provider)
    with pytest.raises(CVExtractionCorrectionError): asyncio.run(service.extract_from_text('CV'))
    assert not calls and service.last_diagnostics.repair['reason'] == 'repair_context_budget_exceeded'


def test_factory_budget_and_exact_only_counter():
    p = create_repair_provider()
    assert p._num_predict == 1024 and p._timeout_seconds == 40 and p._max_retries == 0
    assert p._num_ctx == 10240 and p._safety_margin == 256
    from app.ai.exceptions import AITokenAccountingUnavailableError
    with pytest.raises(AITokenAccountingUnavailableError): asyncio.run(p.token_counter.verify_safe_runtime())


def test_repair_execution_window_cancels_without_second_attempt(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'cv_repair_execution_timeout_seconds', 0.02)
    class Waiting(Sequence):
        async def generate_structured(self, **kwargs):
            self.calls.append(kwargs)
            await asyncio.Event().wait()
    repair = Waiting(); service = CVStructuredExtractionService(Sequence(BAD), repair_provider=repair)
    with pytest.raises(CVExtractionCorrectionError): asyncio.run(service.extract_from_text('CV'))
    assert len(repair.calls) == 1
    assert service.last_diagnostics.repair['reason'] == 'repair_execution_timeout'


def test_exact_accounting_unavailable_cannot_generate_repair():
    from app.ai.exceptions import AITokenAccountingUnavailableError
    class Unknown(ExactRepairCounter):
        async def count(self, payload): raise AITokenAccountingUnavailableError('safe')
    calls=[]
    provider=OllamaProvider(base_url='http://mock.invalid',model='qwen3:8b',num_predict=1024,max_retries=0,
        token_counter=Unknown('http://mock.invalid',40),transport=httpx.MockTransport(lambda r:calls.append(r)))
    with pytest.raises(CVExtractionCorrectionError):
        asyncio.run(CVStructuredExtractionService(Sequence(BAD),repair_provider=provider).extract_from_text('CV'))
    assert calls==[]


@pytest.mark.parametrize('primary', [BAD, {'skills': [{'name': 'Python'}]}])
def test_normal_persistence_only_final_full_valid_result(primary):
    from uuid import UUID
    from app.models.cv import CVSourceType
    from app.services.cv_extraction_service import CandidateCVExtractionService
    from app.schemas.cv_extraction import StructuredCVExtractionResult
    class Reader:
        def extract_uploaded_cv(self, source): return SimpleNamespace(text='CV')
    extractor = CVStructuredExtractionService(Sequence(primary), repair_provider=Sequence(PATCH), text_extraction_service=Reader())
    service = CandidateCVExtractionService.__new__(CandidateCVExtractionService)
    cv = SimpleNamespace(id=UUID(int=1), source_type=CVSourceType.UPLOADED, storage_key='mock', mime_type='application/pdf', original_filename='mock.pdf')
    service._owned_cv_for_update_or_404 = lambda *args: cv
    persisted = []
    def success(identifier, payload, completed):
        StructuredCVExtractionResult.model_validate(payload); persisted.append(payload); return payload
    service.extraction_repository = SimpleNamespace(get_active_for_cv=lambda *a: None, create_processing=lambda *a: None, mark_succeeded=success)
    service.structured_extractor = extractor; service._response = lambda x: x
    result, created = asyncio.run(service.trigger(None, cv.id))
    assert created and len(persisted) == 1 and result == persisted[0]
    assert result['skills'][0]['name'] == 'Python'
