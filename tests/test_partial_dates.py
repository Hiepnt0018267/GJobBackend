"""Shared precision/chronology tests. No providers or database."""
from datetime import date
from types import SimpleNamespace
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.cv import CVExperienceItem, CVEducationItem
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.partial_date import PartialDate
from app.services.matching_input_mapper import build_cv_matching_input
from app.services.matching_fingerprint import fingerprint_cv


@pytest.mark.parametrize('value,expected', [
    ('2022', {'year':2022,'month':None,'day':None,'precision':'year'}),
    ('03/2022', {'year':2022,'month':3,'day':None,'precision':'month'}),
    ('March 2022', {'year':2022,'month':3,'day':None,'precision':'month'}),
    ('2022-03', {'year':2022,'month':3,'day':None,'precision':'month'}),
])
def test_lossless_partial_strings(value, expected):
    item=CVExperienceItem(company_name='Demo',position='Role',start_date=value)
    assert item.model_dump(mode='json')['start_date']==expected


def test_existing_full_date_compatible_and_present_flag():
    item=CVExperienceItem(company_name='Demo',position='Role',start_date='2022-03-17',is_current=True)
    assert item.start_date==date(2022,3,17)
    assert item.model_dump(mode='json')['start_date']=='2022-03-17'
    assert item.end_date is None and item.is_current
    with pytest.raises(ValidationError):
        CVExperienceItem(company_name='Demo',position='Role',end_date='Present')


def test_overlap_is_possible_not_fabricated_comparison():
    item=CVEducationItem(school_name='School',start_date='2022',end_date='March 2022')
    assert item.start_date.precision=='year' and item.start_date.month is None
    assert item.end_date.precision=='month' and item.end_date.day is None
    CVExperienceItem(company_name='Demo',position='Role',start_date='2022-03-17',end_date='2022')


@pytest.mark.parametrize('start,end', [('2023','2021'),('April 2022','March 2022'),('2022-03-18','2022-03-17')])
def test_definitely_reversed_rejected_never_swapped(start,end):
    with pytest.raises(ValidationError):
        CVExperienceItem(company_name='Demo',position='Role',start_date=start,end_date=end)


@pytest.mark.parametrize('value', [
    {'year':2022,'month':1,'precision':'year'},
    {'year':2022,'month':3,'day':1,'precision':'month'},
    {'year':2022,'month':2,'day':30,'precision':'day'},
    {'year':2022,'precision':'day'}, '13/2022', 'unknown',
])
def test_invalid_precision_rejected_not_forced_null(value):
    with pytest.raises(ValidationError):
        CVEducationItem(school_name='School',start_date=value)


def test_day_object_valid_calendar_and_intervals():
    value=PartialDate(year=2024,month=2,day=29,precision='day')
    assert value.interval()==(date(2024,2,29),date(2024,2,29))
    assert PartialDate(year=2024,month=2,precision='month').interval()==(date(2024,2,1),date(2024,2,29))


def test_date_precision_does_not_change_professional_text_or_fingerprint():
    cv=SimpleNamespace(id=uuid.UUID(int=5))
    full=StructuredCVExtractionResult(experiences=[CVExperienceItem(company_name='Demo',position='Developer',start_date='2022-03-17')])
    partial=StructuredCVExtractionResult(experiences=[CVExperienceItem(company_name='Demo',position='Developer',start_date='March 2022')])
    a,b=build_cv_matching_input(cv,full),build_cv_matching_input(cv,partial)
    assert a.semantic_text==b.semantic_text and fingerprint_cv(a)==fingerprint_cv(b)
    assert b.experiences[0].start_date.precision=='month'
