from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID
import pytest
from pydantic import ValidationError
from app.services.cv_source_consistency import validate_source_grounded
from app.schemas.cv import CVExperienceItem
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.matching_input_mapper import build_cv_matching_input
from app.services.matching_fingerprint import fingerprint_cv
from evaluation import prepare_ranking_canonical as prep


def payload(start,end):
    return {'experiences':[{'position':'Developer','company_name':'ABC','description':'Build APIs','start_date':start,'end_date':end}]}


def test_source_conflict_preserved_only_with_verified_context():
    raw=payload('May 2023','March 2023');before=deepcopy(raw)
    cv,audit,conflicts,context=validate_source_grounded('Experience May 2023 to March 2023 Developer ABC Build APIs',raw)
    item=cv.experiences[0]
    assert item.start_date.month==5 and item.end_date.month==3
    assert item.date_consistency.state=='SOURCE_DATA_CONFLICT'
    assert not item.date_consistency.chronology_usable and raw==before
    canonical,minimized=prep.canonical_cv('synthetic',cv,validation_context=context)
    assert 'SOURCE_DATA_CONFLICT' not in canonical.semantic_text
    assert canonical.experiences[0].date_consistency.chronology_usable is False
    with pytest.raises(ValidationError):StructuredCVExtractionResult.model_validate(minimized.model_dump(mode='json'))
    assert StructuredCVExtractionResult.model_validate(minimized.model_dump(mode='json'),context=context).experiences[0].date_consistency
    # Client-provided warning metadata cannot bypass strict chronology.
    forged=minimized.model_dump(mode='json');forged['experiences'][0]['position']='Different role'
    with pytest.raises(ValidationError):StructuredCVExtractionResult.model_validate(forged,context=context)


def test_extraction_contradiction_fails_even_with_source_conflict():
    with pytest.raises(ValueError,match='EXTRACTION_CONTRADICTION'):
        validate_source_grounded('2021 to 2023 Developer ABC Build APIs',payload('2023','2021'))
    with pytest.raises(ValueError,match='EXTRACTION_CONTRADICTION'):
        validate_source_grounded('May 2023 to March 2023 Developer ABC Build APIs',payload('2025','2024'))


def test_normal_and_overlap_strict_behavior_unchanged():
    value,audit,conflicts,context=validate_source_grounded('2021 to 2023 Developer ABC Build APIs',payload('2021','2023'))
    assert not conflicts and 'date_consistency' not in value.model_dump(mode='json')['experiences'][0]
    CVExperienceItem(company_name='ABC',position='Developer',start_date='2022',end_date='March 2022')
    with pytest.raises(ValidationError):CVExperienceItem(company_name='ABC',position='Developer',start_date='2024',end_date='2021')


def test_conflict_metadata_and_dates_do_not_change_matching_signal():
    cv,_,_,context=validate_source_grounded('May 2023 to March 2023 Developer ABC Build APIs',payload('May 2023','March 2023'))
    valid=StructuredCVExtractionResult.model_validate(payload('2021','2023'))
    a=build_cv_matching_input(SimpleNamespace(id=UUID(int=1)),cv)
    b=build_cv_matching_input(SimpleNamespace(id=UUID(int=1)),valid)
    assert a.semantic_text==b.semantic_text and fingerprint_cv(a)==fingerprint_cv(b)
    assert a.experiences[0].date_consistency.chronology_usable is False
    assert a.experiences[0].chronology_range is None
    assert b.experiences[0].chronology_range==(b.experiences[0].start_date,b.experiences[0].end_date)
