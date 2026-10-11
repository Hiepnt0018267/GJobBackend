"""Synthetic contact boundaries; no real source contents or live providers."""
import copy
import uuid
from types import SimpleNamespace

import pytest

from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.matching_text_privacy import (
    sanitize_matching_text as sanitize, find_matching_text_privacy_issues as issues,
    MATCHING_CANONICAL_VERSION,
)
from app.services.matching_input_mapper import build_cv_matching_input, build_job_matching_input
from app.services import matching_fingerprint as fingerprints
from app.services.matching_input_service import MatchingInputService
from app.models.cv import CVSourceType
from app.models.job import JobStatus


@pytest.mark.parametrize('identifier', ['name@example.com', 'NAME@Example.COM',
    'user.name+tag@sub.domain.co.uk', '(one@example.org), two@example.com',
    'Email: name@example.com', 'mailto:name@example.com'])
def test_emails(identifier):
    assert issues(identifier) == ('email',)
    output = sanitize(identifier)
    assert '@' not in output and '[CONTACT]' in output
    assert issues(output) == ()
    assert sanitize(output) == output


@pytest.mark.parametrize('phone', ['+84 912 345 678', '0912 345 678',
    '(028) 1234 5678', '+1-202-555-0101', 'Phone: 202-555-0101',
    'Tel: (202) 555-0101', 'Mobile: 0912345678', '0912345678'])
def test_phone_formats(phone):
    assert issues(phone) == ('phone',)
    output = sanitize(phone)
    assert output == '[CONTACT]'
    assert issues(output) == ()
    assert sanitize(output) == output


@pytest.mark.parametrize('text', ['Python 3.12', '.NET 8', 'AWS EC2', 'ISO 27001',
    '5 years experience', '20% growth', '3-person team', 'REST API HTTP 200',
    'CCNA IELTS 7.0', '2024-2026', 'salary 20-30 million',
    'Salary 1000000000 VND', 'Certificate ID 2025550101', 'contact customers',
    'Certificate ID: 0912345678', 'Salary: +1000000000 USD', 'Quantity: 0912345678',
    'https://docs.python.org/3.12/library/http.html', 'https://github.com/org/repo',
    'https://docs.example.org/api/0912345678?version=0912345678',
    'LinkedIn company: https://linkedin.com/company/demo', 'Version 0.123456789',
    '2024-01-01', 'Quantity: 1234567890', 'Phone support: REST API'])
def test_professional_text_unchanged(text):
    assert sanitize(text) == text
    assert not issues(text)


@pytest.mark.parametrize('url', ['https://www.linkedin.com/in/demo-user',
    'linkedin.com/in/demo-user', 'https://instagram.com/demo',
    'https://t.me/demo', 'https://wa.me/1234567890', 'https://wa.me/0912345678',
    'Portfolio: https://demo.example.org/work', 'https://demo.example.org/contact'])
def test_contact_url(url):
    assert issues(url) == ('contact_url',)
    assert sanitize(url) == '[CONTACT]'
    assert not issues(sanitize(url))


def test_token_boundaries_empty_and_adjacent_career_numbers():
    assert sanitize(None) == sanitize('') == ''
    assert sanitize('API (a@example.com), REST') == 'API ([CONTACT]), REST'
    assert sanitize('Phone: 0912345678 5 years Python 3.12') == '[CONTACT] 5 years Python 3.12'
    assert sanitize('one@example.com\ntwo@example.com') == '[CONTACT]\n[CONTACT]'


def fixture_cv(source_type):
    return SimpleNamespace(id=uuid.UUID(int=1), source_type=source_type,
        personal_info={'full_name': 'Synthetic Person', 'email': 'personal@example.com'},
        career_objective='Develop Python 3.12 APIs. Email: personal@example.com',
        skills=[{'name': 'Python'}], experiences=[{'company_name': 'Demo',
          'position': 'Developer', 'description': '5 years; Phone: 0912345678'}],
        educations=[], projects=[], certificates=[], languages=[])


@pytest.mark.parametrize('mode', ['builder', 'confirmed', 'extracted'])
def test_production_entry_paths_and_raw_immutability(mode):
    cv = fixture_cv(CVSourceType.BUILDER if mode == 'builder' else CVSourceType.UPLOADED)
    original = copy.deepcopy(vars(cv))
    service = object.__new__(MatchingInputService)
    service.cv_repository = SimpleNamespace(get_by_id_for_matching=lambda _: cv)
    structured = {k: v for k, v in vars(cv).items() if k not in {'id', 'source_type'}}
    service.extraction_repository = SimpleNamespace(has_confirmed_for_cv=lambda _: mode=='confirmed',
        get_latest_successful_for_cv=lambda _: SimpleNamespace(structured_result=structured))
    canonical = service.build_cv_input(cv.id)
    assert not issues(canonical.semantic_text)
    assert 'personal@example.com' not in canonical.semantic_text
    assert '0912345678' not in canonical.semantic_text
    assert 'Synthetic Person' not in canonical.semantic_text
    assert '5 years' in canonical.semantic_text and 'Python 3.12' in canonical.semantic_text
    assert vars(cv) == original


def test_fingerprint_version_and_sanitized_text_cache_identity(monkeypatch):
    cv = fixture_cv(CVSourceType.BUILDER)
    canonical = build_cv_matching_input(cv)
    first = fingerprints.fingerprint_cv(canonical)
    assert fingerprints.fingerprint_cv(canonical) == first
    monkeypatch.setattr(fingerprints, 'MATCHING_CANONICAL_VERSION', 'matching-canonical-v1')
    assert fingerprints.fingerprint_cv(canonical) != first
    old = canonical.model_copy(update={'semantic_text': cv.career_objective})
    assert fingerprints.fingerprint_cv(old) != first
    assert MATCHING_CANONICAL_VERSION == 'matching-canonical-v3-explicit-identity-contract'


def test_noncontact_mapper_text_equivalence(monkeypatch):
    from app.services import matching_input_mapper as mapper
    cv = fixture_cv(CVSourceType.BUILDER)
    cv.career_objective = 'Python 3.12 .NET 8 HTTP 200'
    cv.experiences[0]['description'] = '2024-2026, 20% growth; ISO 27001'
    sanitized = mapper.build_cv_matching_input(cv)
    monkeypatch.setattr(mapper, 'sanitize_matching_text', lambda x: x)
    assert mapper.build_cv_matching_input(cv).semantic_text == sanitized.semantic_text


def fixture_job():
    return SimpleNamespace(id=uuid.UUID(int=2), title='Python Developer',
        description='5 years. Email: recruiting@example.com',
        requirements='REST API .NET 8; Tel: +1-202-555-0101', skills=['Python 3.12'],
        location=None, industry=None, employment_type=None, experience_level=None,
        level=None, experience_requirement=None, work_mode=None, status=JobStatus.APPROVED,
        salary_type=None, salary_min=None, salary_max=None, salary_fixed=None,
        salary_currency='USD', vacancies=1)


def test_jd_mapper_all_sections_and_raw_preservation():
    job = fixture_job()
    original = copy.deepcopy(vars(job))
    canonical = build_job_matching_input(job)
    assert not issues(canonical.semantic_text)
    assert 'recruiting@example.com' not in canonical.semantic_text
    assert '202-555-0101' not in canonical.semantic_text
    assert '5 years' in canonical.semantic_text
    assert '.NET 8' in canonical.semantic_text and 'Python 3.12' in canonical.semantic_text
    assert vars(job) == original
    assert canonical.description == job.description
    assert canonical.requirements == job.requirements


def test_job_cache_version_separation(monkeypatch):
    canonical = build_job_matching_input(fixture_job())
    first = fingerprints.fingerprint_job(canonical)
    assert fingerprints.fingerprint_job(canonical) == first
    monkeypatch.setattr(fingerprints, 'MATCHING_CANONICAL_VERSION', 'matching-canonical-v1')
    assert fingerprints.fingerprint_job(canonical) != first
