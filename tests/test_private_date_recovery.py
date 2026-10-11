import asyncio
import json
from types import SimpleNamespace
from pathlib import Path
import httpx
import pytest
from pydantic import ValidationError
from app.ai.ollama_provider import OllamaProvider
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.cv import CVExperienceItem
from app.schemas.partial_date import OpenEndedDate, PartialDate
from app.services.cv_structured_extraction_service import CVStructuredExtractionService
from app.services.cv_date_evidence import ground_structured_dates, resolve_date_evidence
from app.services.cv_source_consistency import validate_source_grounded
from evaluation.recovery_checkpoint import PrivateStructuredCheckpoint
from evaluation import prepare_ranking_canonical as prep


def test_raw_persisted_before_failed_validation_then_no_model_recovery(tmp_path):
    checkpoint=PrivateStructuredCheckpoint(tmp_path/'private.json',{'cv_id':'synthetic','source_sha256':'hash','provider':'ollama','model':'qwen3:8b'})
    checkpoint.start_generation()
    raw={'experiences':[{'company_name':'Demo','position':'Engineer','start_date':'2024','end_date':'2021'}]}
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'done':True,'done_reason':'stop','message':{'content':json.dumps(raw)}})
    from app.ai.ollama_token_budget import PromptAccounting
    class Counter:
        async def count(self, payload): return PromptAccounting(100,0,8192)
    provider=OllamaProvider(base_url='http://mock.invalid',model='qwen3:8b',max_retries=0,transport=httpx.MockTransport(respond),structured_response_observer=checkpoint.capture,token_counter=Counter())
    in_request = asyncio.run(
        CVStructuredExtractionService(provider=provider,max_schema_retries=0)
        .extract_from_text('2024 to 2021 Engineer Demo')
    )
    assert in_request.experiences[0].date_consistency.chronology_usable is False
    assert len(calls)==1
    assert checkpoint.payload()==raw
    accepted,audit,conflicts,context=validate_source_grounded('2024 to 2021 Engineer Demo',checkpoint.payload())
    assert accepted.experiences[0].date_consistency.chronology_usable is False
    assert len(conflicts)==1 and len(calls)==1
    checkpoint.result('DETERMINISTIC_VALIDATION_PASS')
    assert 'raw_structured_response' in json.loads(checkpoint.path.read_text())
    canonical,minimized=prep.canonical_cv('synthetic',accepted)
    public={'canonical_input':canonical.model_dump(mode='json'),'structured_result':minimized.model_dump(mode='json')}
    assert 'raw_structured_response' not in json.dumps(public)
    assert 'raw_structured_response' not in json.dumps(public)
    with pytest.raises(RuntimeError):checkpoint.start_generation()


@pytest.mark.parametrize('expression,precision', [('2020 to 2022','year'),('03/2020 to 03/2022','month'),('March 2020 to March 2022','month'),('2020-03-17 to 2022-03-18','day')])
def test_local_verified_range(expression,precision):
    start,end,_=resolve_date_evidence(expression+' Engineer Demo',{'position':'Engineer','company_name':'Demo'},anchor_field='position',secondary_field='company_name')
    assert (end.precision if isinstance(end,PartialDate) else 'day')==precision


def test_unrelated_global_years_do_not_match():
    with pytest.raises(ValueError):
        resolve_date_evidence('Other 2020 to 2022 '+('unrelated prose '*50)+' Engineer Demo',{'position':'Engineer','company_name':'Demo'},anchor_field='position',secondary_field='company_name')


def test_ambiguous_local_year_non_null_chronology_possible():
    payload={'experiences':[{'position':'Engineer','company_name':'Demo','start_date':'2022','end_date':'2022-03'}]}
    recovered,_=ground_structured_dates('Engineer Demo 2022',payload)
    value=StructuredCVExtractionResult.model_validate(recovered).experiences[0]
    assert value.end_date.precision=='ambiguous' and value.end_date.month is None
    assert payload['experiences'][0]['end_date']=='2022-03'
    with pytest.raises(ValidationError):
        CVExperienceItem(position='Engineer',company_name='Demo',start_date='2024',end_date={'year':2021,'precision':'ambiguous'})


def test_absent_or_multiple_local_ranges_fail_without_mutation():
    with pytest.raises(ValidationError):
        CVExperienceItem(position='Engineer',company_name='Demo',end_date={})
    record={'position':'Engineer','company_name':'Demo','end_date':'2022'}
    for source in ['Engineer Demo no dates','2020 to 2022 Engineer Demo 2021 to 2023']:
        with pytest.raises(ValueError):resolve_date_evidence(source,record,anchor_field='position',secondary_field='company_name')
    assert record['end_date']=='2022'
