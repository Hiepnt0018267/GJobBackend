import asyncio
import pytest
from pydantic import ValidationError
from app.schemas.cv import CVEducationItem, CVExperienceItem, CVSkillItem
from app.ai.exceptions import AIProviderError
from app.services.cv_structured_extraction_service import CVStructuredExtractionService, CVExtractionValidationError, CVAIProviderUnavailableError
from app.services.matching_text_privacy import identity_fields_influence_matching


def test_nullable_blank_safe_normalization_not_required_fields():
    edu=CVEducationItem(school_name='School',field_of_study='  ',description='')
    assert edu.field_of_study is None and edu.description is None
    assert CVExperienceItem(company_name='Company',position='Role',description=' ').description is None
    with pytest.raises(ValidationError): CVSkillItem(name=' ')
    with pytest.raises(ValidationError): CVEducationItem(school_name=' ')
    with pytest.raises(ValidationError): CVEducationItem(school_name='School',field_of_study={})


def test_bad_dates_not_coerced_swapped_or_fabricated():
    for dates in [dict(start_date='2020-01-01',end_date='2010-01-01'),dict(end_date='Present')]:
        with pytest.raises(ValidationError): CVExperienceItem(company_name='C',position='R',**dates)


class SequenceProvider:
    def __init__(self,values): self.values=iter(values);self.prompts=[]
    async def generate_structured(self,**kwargs):
        self.prompts.append(kwargs)
        item=next(self.values)
        if isinstance(item,Exception): raise item
        return item


def test_one_correction_retry_same_source_schema_no_private_errors():
    provider=SequenceProvider([{'skills':[{'name':'Python','level':'advanced'}]}])
    repair=SequenceProvider([{'repairs':[{'path':['skills',0,'level'],'value':'ADVANCED'}]}])
    result=asyncio.run(CVStructuredExtractionService(provider=provider,repair_provider=repair).extract_from_text('CV ONLY SOURCE'))
    assert result.skills[0].name=='Python' and len(provider.prompts)==len(repair.prompts)==1
    assert 'CV ONLY SOURCE' in provider.prompts[0]['prompt']
    assert 'CV ONLY SOURCE' not in repair.prompts[0]['prompt']
    assert result.skills[0].level.value=='ADVANCED'


def test_invalid_after_retry_rejected_bounded():
    provider=SequenceProvider([{'skills':{}},{'skills':{}}])
    with pytest.raises(CVExtractionValidationError):
        asyncio.run(CVStructuredExtractionService(provider=provider).extract_from_text('CV'))
    assert len(provider.prompts)==1


def test_final_correction_one_call_only():
    provider=SequenceProvider([{'skills':{}}])
    with pytest.raises(ValueError,match='correction-only'):
        CVStructuredExtractionService(provider=provider,correction_only=True)
    assert len(provider.prompts)==0


def test_unavailable_not_schema_retried():
    provider=SequenceProvider([AIProviderError('private')])
    with pytest.raises(CVAIProviderUnavailableError):
        asyncio.run(CVStructuredExtractionService(provider=provider).extract_from_text('CV'))
    assert len(provider.prompts)==1


def test_provenance_audit_preserves_role_overlap_detects_structural_leak():
    assert not identity_fields_influence_matching('Senior Backend Engineer','Senior Backend Engineer')
    assert identity_fields_influence_matching('Nguyen Van A Python','Python')
