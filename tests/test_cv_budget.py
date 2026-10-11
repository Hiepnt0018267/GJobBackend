"""Synthetic budget/deadline tests: no live model, raw CV or DEV database."""
import asyncio
import json
import time
from types import SimpleNamespace
import httpx
import pytest
from pydantic import BaseModel
from app.ai.exceptions import (AIContextBudgetExceededError, AIOutputBudgetExceededError,
    AITokenAccountingUnavailableError, AIJSONParseError, AISchemaValidationError, AITimeoutError)
from app.ai.ollama_provider import OllamaProvider
from app.ai.ollama_token_budget import PromptAccounting
from app.core.config import settings
from app.services.cv_structured_extraction_service import (CVStructuredExtractionService,
    CVExtractionDeadlineError, CVExtractionCorrectionError, CVAIProviderTimeoutError,
    CVAIContextBudgetError, CVAIOutputBudgetError, CVExtractionJSONError, CVExtractionSchemaError)

class Result(BaseModel):
    name: str

class Counter:
    def __init__(self,n,special=2,ctx=8192): self.n=n;self.special=special;self.ctx=ctx;self.verified=0
    async def count(self,payload):
        assert payload['options']['num_predict']==4608
        if self.n is None: raise AITokenAccountingUnavailableError('synthetic unavailable')
        return PromptAccounting(self.n,self.special,self.ctx)
    async def verify_safe_runtime(self): self.verified+=1

def provider(counter,handler):
    return OllamaProvider(base_url='http://mock.test',model='qwen3:8b',timeout_seconds=1,
        transport=httpx.MockTransport(handler),token_counter=counter,num_predict=4608,safety_margin=256)

def response(content='{"name":"A"}',**extra):
    return httpx.Response(200,json={'done':True,'done_reason':'stop','prompt_eval_count':100,
        'eval_count':20,'message':{'content':content},**extra})

@pytest.mark.parametrize('tokens,allowed',[(3325,True),(3326,True),(3327,False)])
def test_fit_exact_boundary_overflow_never_generates(tokens,allowed):
    calls=[]
    def generate(request): calls.append(json.loads(request.content));return response(prompt_eval_count=tokens)
    p=provider(Counter(tokens),generate)
    if allowed: assert asyncio.run(p.generate_structured('CV',Result)).name=='A'
    else:
        with pytest.raises(AIContextBudgetExceededError): asyncio.run(p.generate_structured('CV',Result))
    assert len(calls)==int(allowed)
    if calls: assert not calls[0]['shift'] and not calls[0]['truncate']

def test_unavailable_exact_count_heuristic_never_blocks(caplog):
    counter=Counter(None);calls=[];p=provider(counter,lambda r:calls.append(r) or response())
    assert asyncio.run(p.generate_structured('CV'*20000,Result)).name=='A'
    assert len(calls)==1 and counter.verified==1 and p.last_accounting is None
    assert 'APPROXIMATE' in caplog.text and 'CV'*10 not in caplog.text

def test_unknown_runtime_safety_is_not_a_cv_size_error():
    class Unsafe(Counter):
        async def verify_safe_runtime(self): raise AITokenAccountingUnavailableError('unsupported safety flags')
    calls=[];p=provider(Unsafe(None),lambda r:calls.append(r) or response())
    with pytest.raises(AITokenAccountingUnavailableError): asyncio.run(p.generate_structured('CV',Result))
    assert calls==[]

@pytest.mark.parametrize('body',[response('{',eval_count=4608),response('{',done_reason='length'),response(eval_count=4609)])
def test_output_limit_is_typed_and_not_retried(body):
    calls=[];p=provider(Counter(100),lambda r:calls.append(r) or body)
    with pytest.raises(AIOutputBudgetExceededError): asyncio.run(p.generate_structured('CV',Result))
    assert len(calls)==1

def test_complete_schema_valid_json_with_normal_stop_at_cap():
    assert asyncio.run(provider(Counter(100),lambda r:response(eval_count=4608)).generate_structured('CV',Result)).name=='A'

@pytest.mark.parametrize('ctx,allowed',[(8192,False),(10240,True)])
def test_installed_capacity_contract_admits_original3928_prompt_only_with_headroom(ctx,allowed):
    calls=[];source='Full unchanged CV source'
    def generated(request):
        payload=json.loads(request.content);calls.append(payload)
        assert payload['options']=={'num_ctx':ctx,'num_predict':4608,'temperature':0.0}
        assert payload['messages'][0]['content'].startswith(source)
        return response(prompt_eval_count=3928)
    p=OllamaProvider(base_url='http://mock.test',model='qwen3:8b',num_ctx=ctx,num_predict=4608,
        safety_margin=256,token_counter=Counter(3928,0,ctx),transport=httpx.MockTransport(generated))
    if allowed:assert asyncio.run(p.generate_structured(source,Result)).name=='A'
    else:
        with pytest.raises(AIContextBudgetExceededError):asyncio.run(p.generate_structured(source,Result))
    assert len(calls)==int(allowed)

def test_extraction_context_changes_profile_not_embedding_configuration():
    from app.ai.factory import create_ai_provider
    p=create_ai_provider()
    assert p._num_ctx==10240 and p._num_predict==4608 and p._safety_margin==256
    assert p.structured_profile['shift'] is False and p.structured_profile['truncate'] is False
    old=OllamaProvider(base_url=p._base_url,model=p._model,num_ctx=8192,num_predict=4608,
        safety_margin=256,timeout_seconds=p._timeout_seconds)
    assert old.structured_profile_fingerprint!=p.structured_profile_fingerprint
    assert settings.embedding_num_ctx==8192 and settings.embedding_num_batch==4096
    assert p._timeout_seconds==165
    assert settings.cv_extraction_total_timeout_seconds==230
    assert settings.cv_extraction_network_margin_seconds==20
    assert settings.cv_repair_provider_timeout_seconds==40
    assert settings.cv_repair_execution_timeout_seconds==50

@pytest.mark.parametrize('content,error',[('{',AIJSONParseError),('{}',AISchemaValidationError)])
def test_json_and_schema_failures_distinct(content,error):
    with pytest.raises(error): asyncio.run(provider(Counter(100),lambda r:response(content)).generate_structured('CV',Result))

def test_runtime_context_rejection_is_not_retried():
    from app.ai.exceptions import AIContextLimitError
    calls=[];p=provider(Counter(None),lambda r:calls.append(r) or httpx.Response(500,json={'error':'exceeds context size'}))
    with pytest.raises(AIContextLimitError): asyncio.run(p.generate_structured('CV',Result))
    assert len(calls)==1

class Sequence:
    def __init__(self,values,delay=0): self.values=iter(values);self.calls=0;self.delay=delay
    async def generate_structured(self,**kwargs):
        self.calls+=1
        if self.delay: await asyncio.sleep(self.delay)
        value=next(self.values)
        if isinstance(value,Exception): raise value
        return value

def test_insufficient_correction_budget_does_not_start_second_call(monkeypatch):
    monkeypatch.setattr(settings,'cv_extraction_total_timeout_seconds',.1)
    monkeypatch.setattr(settings,'cv_extraction_correction_min_seconds',.09)
    p=Sequence([{'skills':[{'name':'Python','level':'advanced'}]}],.02);s=CVStructuredExtractionService(p)
    with pytest.raises(CVExtractionDeadlineError): asyncio.run(s.extract_from_text('CV'))
    assert p.calls==1 and s.schema_retries==0

def test_total_deadline_bounds_slow_provider(monkeypatch):
    monkeypatch.setattr(settings,'cv_extraction_total_timeout_seconds',.03)
    p=Sequence([{}],.5);start=time.perf_counter()
    with pytest.raises(CVExtractionDeadlineError): asyncio.run(CVStructuredExtractionService(p).extract_from_text('CV'))
    assert time.perf_counter()-start<.2 and p.calls==1

@pytest.mark.parametrize('failure,mapped',[(AITimeoutError('safe'),CVAIProviderTimeoutError),
    (AIOutputBudgetExceededError('safe'),CVAIOutputBudgetError),(AIContextBudgetExceededError('safe'),CVAIContextBudgetError),
    (AIJSONParseError('safe'),CVExtractionJSONError),(AISchemaValidationError('safe'),CVExtractionSchemaError)])
def test_failure_taxonomy_without_schema_retry(failure,mapped):
    p=Sequence([failure]);s=CVStructuredExtractionService(p,max_schema_retries=0)
    with pytest.raises(mapped): asyncio.run(s.extract_from_text('CV'))
    assert p.calls==1

def test_correction_failure_is_distinct_and_bounded():
    p=Sequence([{'skills':[{'name':'Python','level':'advanced'}]}]);repair=Sequence([AIJSONParseError('bad')])
    s=CVStructuredExtractionService(p,repair_provider=repair)
    with pytest.raises(CVExtractionCorrectionError): asyncio.run(s.extract_from_text('CV'))
    assert p.calls==1 and repair.calls==1 and s.schema_retries==1

def test_public_policy_centralizes_deadline_and_network_margin():
    from app.routers.cvs import cv_extraction_policy
    p=cv_extraction_policy(None)
    assert p['operation_timeout_ms']==settings.cv_extraction_total_timeout_seconds*1000
    assert p['request_timeout_ms']==(settings.cv_extraction_total_timeout_seconds+settings.cv_extraction_network_margin_seconds)*1000
    assert p['request_timeout_ms']>p['operation_timeout_ms']
    assert p=={'operation_timeout_ms':230000,'request_timeout_ms':250000}

def test_primary_near_timeout_succeeds_with_operation_budget_remaining(monkeypatch):
    import app.services.cv_structured_extraction_service as svc
    clock=[0.0]
    monkeypatch.setattr(svc,'time',SimpleNamespace(perf_counter=lambda:clock[0]))
    monkeypatch.setattr(svc.settings,'cv_extraction_total_timeout_seconds',230.0)
    class NearLimit:
        calls=0
        async def generate_structured(self,**kwargs):
            self.calls+=1;clock[0]=160.0
            return {'personal_info':{'full_name':'Synthetic'}}
    provider=NearLimit();service=CVStructuredExtractionService(provider,max_schema_retries=0)
    result=asyncio.run(service.extract_from_text('CV'))
    assert result.personal_info.full_name=='Synthetic'
    assert provider.calls==1 and 230-clock[0]==70

def test_post_generation_work_cannot_extend_total_deadline(monkeypatch):
    import app.services.cv_structured_extraction_service as svc
    clock=[0.0]
    monkeypatch.setattr(svc,'time',SimpleNamespace(perf_counter=lambda:clock[0]))
    monkeypatch.setattr(svc.settings,'cv_extraction_total_timeout_seconds',230.0)
    class PastDeadline:
        calls=0
        async def generate_structured(self,**kwargs):
            self.calls+=1;clock[0]=231.0
            return {'personal_info':{'full_name':'Synthetic'}}
    provider=PastDeadline();service=CVStructuredExtractionService(provider,max_schema_retries=0)
    with pytest.raises(CVExtractionDeadlineError,match='Validation exceeded'):
        asyncio.run(service.extract_from_text('CV'))
    assert provider.calls==1 and service.schema_retries==0

def test_primary_timeout_is_typed_and_never_starts_repair():
    primary=Sequence([AITimeoutError('synthetic timeout')]);repair=Sequence([])
    service=CVStructuredExtractionService(primary,repair_provider=repair)
    with pytest.raises(CVAIProviderTimeoutError):
        asyncio.run(service.extract_from_text('CV'))
    assert primary.calls==1 and repair.calls==0 and service.schema_retries==0

def test_runtime_counter_renders_and_tokenizes_same_model_without_completion(monkeypatch):
    from app.ai.ollama_token_budget import OllamaRuntimeTokenCounter
    original_client=httpx.AsyncClient;calls=[]
    def handle(request):
        calls.append(request.url.path)
        if request.url.path=='/api/version': return httpx.Response(200,json={'version':'0.34.2'})
        if request.url.path=='/api/show': return httpx.Response(200,json={'modelfile':'FROM synthetic.gguf','model_info':{'general.architecture':'qwen3','qwen3.context_length':40960}})
        if request.url.path=='/api/chat':
            assert json.loads(request.content)['_debug_render_only'] is True
            return httpx.Response(200,json={'_debug_info':{'rendered_template':'same exact template'}})
        if request.url.path=='/props': return httpx.Response(200,json={'model_path':'synthetic.gguf'})
        if request.url.path=='/tokenize':
            body=json.loads(request.content);assert body['content']=='same exact template'
            return httpx.Response(200,json={'tokens':[1]*(12 if body['add_special'] else 10)})
        pytest.fail('Unexpected runtime request')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original_client(transport=httpx.MockTransport(handle),**kwargs))
    async def commands():return ['llama-server --port 1234 --ctx-size 8192 --parallel 1']
    monkeypatch.setattr(OllamaRuntimeTokenCounter,'_runner_commands',staticmethod(commands))
    p={'model':'qwen3:8b','options':{'num_ctx':8192},'messages':[]}
    counted=asyncio.run(OllamaRuntimeTokenCounter('http://localhost:11434',2).count(p))
    assert counted==PromptAccounting(10,2,8192) and calls.count('/api/chat')==1
    assert '_debug_render_only' not in p

def test_output_context_failures_do_not_start_correction():
    for failure,mapped in [(AIOutputBudgetExceededError('cap'),CVAIOutputBudgetError),(AIContextBudgetExceededError('context'),CVAIContextBudgetError)]:
        p=Sequence([failure,{}])
        with pytest.raises(mapped):asyncio.run(CVStructuredExtractionService(p).extract_from_text('CV'))
        assert p.calls==1

def test_terminal_failure_codes_are_safe_and_distinct():
    from types import SimpleNamespace as NS
    from uuid import UUID
    from fastapi import HTTPException
    from app.models.cv import CVSourceType
    from app.services.cv_extraction_service import CandidateCVExtractionService
    cases=[(CVAIProviderTimeoutError('private'),504,'AI_PROVIDER_TIMEOUT'),
        (CVExtractionDeadlineError('private'),504,'AI_OPERATION_DEADLINE_EXCEEDED'),
        (CVAIOutputBudgetError('private'),502,'AI_OUTPUT_BUDGET_EXCEEDED'),
        (CVAIContextBudgetError('private'),422,'AI_CONTEXT_BUDGET_EXCEEDED'),
        (CVExtractionJSONError('private'),502,'AI_JSON_INVALID'),
        (CVExtractionSchemaError('private'),502,'AI_SCHEMA_INVALID'),
        (CVExtractionCorrectionError('private'),502,'AI_CORRECTION_FAILED')]
    for failure,status,code in cases:
        s=CandidateCVExtractionService.__new__(CandidateCVExtractionService)
        c=NS(id=UUID(int=1),source_type=CVSourceType.UPLOADED,storage_key='synthetic.pdf',mime_type='application/pdf',original_filename='synthetic.pdf')
        s._owned_cv_for_update_or_404=lambda *args:c
        s.extraction_repository=NS(get_active_for_cv=lambda *a:None,create_processing=lambda *a:None)
        failed=[];s._persist_failure=lambda *args:failed.append(args)
        class Extractor:
            async def extract_uploaded_cv(self,*a):raise failure
        s.structured_extractor=Extractor()
        with pytest.raises(HTTPException) as error:asyncio.run(s.trigger(None,c.id))
        assert error.value.status_code==status and error.value.detail['code']==code
        assert failed[0][1]==code and 'private' not in str(error.value.detail)

def test_primary_timeout_never_persists_partial_success_payload():
    from types import SimpleNamespace as NS
    from uuid import UUID
    from fastapi import HTTPException
    from app.models.cv import CVSourceType
    from app.services.cv_extraction_service import CandidateCVExtractionService
    calls={'processing':0,'failed':[],'succeeded':[]}
    repository=NS(
        get_active_for_cv=lambda *a:None,
        create_processing=lambda *a:calls.__setitem__('processing',calls['processing']+1),
        mark_failed=lambda *a:calls['failed'].append(a),
        mark_succeeded=lambda *a:calls['succeeded'].append(a),
    )
    service=CandidateCVExtractionService.__new__(CandidateCVExtractionService)
    cv=NS(id=UUID(int=2),source_type=CVSourceType.UPLOADED,storage_key='synthetic.pdf',
        mime_type='application/pdf',original_filename='synthetic.pdf')
    service._owned_cv_for_update_or_404=lambda *args:cv
    service.extraction_repository=repository
    class TimedOut:
        async def extract_uploaded_cv(self,*a):raise CVAIProviderTimeoutError('private')
    service.structured_extractor=TimedOut()
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.trigger(None,cv.id))
    assert error.value.status_code==504
    assert calls['processing']==1 and len(calls['failed'])==1
    assert calls['failed'][0][1]=='AI_PROVIDER_TIMEOUT'
    assert calls['succeeded']==[]
