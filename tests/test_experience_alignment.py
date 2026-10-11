import copy
import pytest
from pydantic import ValidationError
from app.services.cv_experience_alignment import align_experiences_to_source,company_tokens
from app.services.cv_date_evidence import ground_structured_dates
from app.schemas.cv_extraction import StructuredCVExtractionResult


def item(role='Developer',company='ABC',description='Build APIs',**dates):
    return dict(position=role,company_name=company,description=description,**dates)


def test_alias_tokens_and_exact_range():
    assert company_tokens('ABC Ltd.')==company_tokens('ABC Limited')==company_tokens('ABC')
    assert company_tokens('XYZ')!=company_tokens('ABC')
    result=align_experiences_to_source([item()], 'Experience 2021 to 2023 Developer ABC Ltd. Build APIs Education 2020 Bachelor degree')
    assert len(result)==1 and result[0]['components']['company']==1000


def test_unique_role_and_responsibilities_can_disambiguate_company_mismatch():
    result=align_experiences_to_source([item(company='Different legal formatting')], 'Experience 2021 to Current Developer ABC Build APIs')
    assert result[0]['components']['company']==0
    assert result[0]['components']['responsibilities']==1000
    with pytest.raises(ValueError):
        align_experiences_to_source([item(company='Unknown',description='Unrelated sales')], '2021 to 2023 Developer ABC Build APIs')


def test_repeated_roles_global_one_to_one_and_reverse_chronological_document():
    rows=[item(company='ABC',description='Build APIs'),item(company='XYZ',description='Maintain SQL')]
    text='Experience 2022 to Current Developer ABC Build APIs 2019 to 2021 Developer XYZ Maintain SQL Education 2018 Bachelor'
    result=align_experiences_to_source(rows,text)
    assert [r['source_candidate_index'] for r in result]==[0,1]
    assert len({tuple(r['range_offsets']) for r in result})==2
    with pytest.raises(ValueError):align_experiences_to_source(rows,'2022 to Current Developer ABC Build APIs')


def test_same_company_distinct_seniority_and_role():
    rows=[item('Senior Developer'),item('Data Analyst',description='Analyze data')]
    result=align_experiences_to_source(rows,'2021 to Current Senior Developer ABC Build APIs 2018 to 2020 Data Analyst ABC Analyze data')
    assert all(r['components']['role']==1000 for r in result)


def test_duplicate_equivalent_dates_safe_tie_distinct_dates_not_safe():
    source='2021 to 2023 Developer ABC Build APIs 2021 to 2023 Developer ABC Build APIs'
    result=align_experiences_to_source([item()],source)
    assert result[0]['status']=='equivalent_date_tie'
    with pytest.raises(ValueError,match='AMBIGUOUS'):
        align_experiences_to_source([item()],source.replace('2021 to 2023 Developer ABC Build APIs', '2020 to 2022 Developer ABC Build APIs',1))
    with pytest.raises(ValueError,match='AMBIGUOUS'):
        align_experiences_to_source([item()],source+' 2019 to 2020 Developer ABC Build APIs')


def test_partial_current_and_unrelated_education():
    source='Experience March 2021 to Current Developer ABC Build APIs Education 2000 to 2004 University degree'
    payload={'experiences':[item(start_date='2021',end_date='2023')]}
    result,audit=ground_structured_dates(source,payload)
    cv=StructuredCVExtractionResult.model_validate(result)
    assert cv.experiences[0].start_date.precision=='month'
    assert cv.experiences[0].end_date.state=='current'
    assert len(audit)==1


def test_new_policy_provider_swap_is_extraction_contradiction():
    payload={'experiences':[item(start_date='2023',end_date='2021')]};original=copy.deepcopy(payload)
    with pytest.raises(ValueError,match='EXTRACTION_CONTRADICTION'):
        ground_structured_dates('2021 to 2023 Developer ABC Build APIs',payload)
    assert payload==original
    invalid,_=ground_structured_dates('2023 to 2021 Developer ABC Build APIs',payload)
    with pytest.raises(ValidationError):StructuredCVExtractionResult.model_validate(invalid)
    with pytest.raises(ValueError):ground_structured_dates('Developer ABC dates unknown Build APIs',payload)
