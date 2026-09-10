"""
Task 04 -- Job Listing & Search tests
Run: pytest tests/test_jobs.py -v
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.models.job import (
    EmploymentType,
    ExperienceLevel,
    ExperienceRequirement,
    Industry,
    Job,
    JobLevel,
    JobStatus,
    SalaryType,
    WorkMode,
)
from app.models.recruiter_profile import RecruiterProfile
from app.models.user import User, UserRole

client = TestClient(app)

BASE = "/api/v1/jobs"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _db() -> Session:
    return SessionLocal()


def _create_job(
    title: str = "Python Developer",
    company_name: str = "Test Corp",
    location: str = "Ha Noi",
    employment_type: EmploymentType = EmploymentType.FULL_TIME,
    experience_level: ExperienceLevel = ExperienceLevel.MID,
    salary_min: int = 10_000_000,
    salary_max: int = 20_000_000,
    skills: list = None,
    status: JobStatus = JobStatus.APPROVED,
    industry: Industry | None = None,
    experience_requirement: ExperienceRequirement | None = None,
    level: JobLevel | None = None,
    work_mode: WorkMode | None = None,
    salary_type: SalaryType | None = None,
    salary_fixed: int | None = None,
    recruiter_id: uuid.UUID | None = None,
) -> Job:
    """Insert a job directly into DB for testing."""
    db = _db()
    job = Job(
        recruiter_id=recruiter_id,
        title=title,
        description=f"Description for {title}",
        company_name=company_name,
        location=location,
        employment_type=employment_type,
        experience_level=experience_level,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_type=salary_type,
        salary_fixed=salary_fixed,
        industry=industry,
        experience_requirement=experience_requirement,
        level=level,
        work_mode=work_mode,
        skills=skills or ["Python", "FastAPI"],
        status=status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    db.close()
    return job


def _delete_job(job_id: uuid.UUID) -> None:
    db = _db()
    db.query(Job).filter(Job.id == job_id).delete()
    db.commit()
    db.close()


# ── Basic listing ─────────────────────────────────────────────────────────────

def test_list_jobs_200():
    """GET /jobs returns 200 with pagination envelope."""
    resp = client.get(BASE)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert "total_pages" in data


def test_list_jobs_default_pagination():
    resp = client.get(BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 10


def test_list_jobs_custom_pagination():
    resp = client.get(BASE, params={"page": 2, "page_size": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["page_size"] == 5


def test_list_jobs_invalid_page():
    resp = client.get(BASE, params={"page": 0})
    assert resp.status_code == 422


def test_list_jobs_invalid_page_size_zero():
    resp = client.get(BASE, params={"page_size": 0})
    assert resp.status_code == 422


def test_list_jobs_invalid_page_size_over_100():
    resp = client.get(BASE, params={"page_size": 101})
    assert resp.status_code == 422


def test_list_jobs_salary_min_gt_max_422():
    resp = client.get(BASE, params={"salary_min": 20_000_000, "salary_max": 10_000_000})
    assert resp.status_code == 422


# ── Public status filtering ───────────────────────────────────────────────────

def test_pending_job_not_in_public_listing():
    job = _create_job(title="Pending Job Unique XYZ", status=JobStatus.PENDING)
    try:
        resp = client.get(BASE, params={"keyword": "Pending Job Unique XYZ"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) not in ids, "PENDING job must not appear in public listing"
    finally:
        _delete_job(job.id)


def test_rejected_job_not_in_public_listing():
    job = _create_job(title="Rejected Job Unique XYZ", status=JobStatus.REJECTED)
    try:
        resp = client.get(BASE, params={"keyword": "Rejected Job Unique XYZ"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) not in ids, "REJECTED job must not appear in public listing"
    finally:
        _delete_job(job.id)


def test_approved_job_in_public_listing():
    job = _create_job(title="Approved Job Unique XYZ123", status=JobStatus.APPROVED)
    try:
        resp = client.get(BASE, params={"keyword": "Approved Job Unique XYZ123"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids, "APPROVED job must appear in public listing"
    finally:
        _delete_job(job.id)


# ── Search ────────────────────────────────────────────────────────────────────

def test_keyword_search_by_title():
    job = _create_job(title="SeniorRustEngineerUniqueKW", status=JobStatus.APPROVED)
    try:
        resp = client.get(BASE, params={"keyword": "SeniorRustEngineerUniqueKW"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_keyword_search_by_company():
    job = _create_job(
        title="Some Developer",
        company_name="UniqueCompanyNameXYZ42",
        status=JobStatus.APPROVED,
    )
    try:
        resp = client.get(BASE, params={"keyword": "UniqueCompanyNameXYZ42"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_keyword_search_by_skills():
    job = _create_job(
        title="Some Job",
        skills=["GoLangUniqueSkill", "Docker"],
        status=JobStatus.APPROVED,
    )
    try:
        resp = client.get(BASE, params={"keyword": "GoLangUniqueSkill"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


# ── Filters ───────────────────────────────────────────────────────────────────

def test_location_filter():
    job = _create_job(title="HCM Job Unique", location="Ho Chi Minh", status=JobStatus.APPROVED)
    try:
        resp = client.get(BASE, params={"location": "Ho Chi Minh"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_employment_type_filter():
    job = _create_job(
        title="Internship Unique XYZ",
        employment_type=EmploymentType.INTERNSHIP,
        status=JobStatus.APPROVED,
    )
    try:
        resp = client.get(BASE, params={"employment_type": "INTERNSHIP", "keyword": "Internship Unique XYZ"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_experience_level_filter():
    job = _create_job(
        title="Senior Dev Unique XYZ",
        experience_level=ExperienceLevel.SENIOR,
        status=JobStatus.APPROVED,
    )
    try:
        resp = client.get(BASE, params={"experience_level": "SENIOR", "keyword": "Senior Dev Unique XYZ"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_salary_filter():
    job = _create_job(
        title="HighSalary Job Unique XYZ",
        salary_min=30_000_000,
        salary_max=50_000_000,
        status=JobStatus.APPROVED,
    )
    try:
        resp = client.get(BASE, params={"salary_min": 25_000_000, "keyword": "HighSalary Job Unique XYZ"})
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_combined_filters():
    job = _create_job(
        title="FullStack Dev Combined",
        company_name="Combined Corp",
        location="Da Nang",
        employment_type=EmploymentType.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        skills=["React", "Node"],
        status=JobStatus.APPROVED,
    )
    try:
        resp = client.get(BASE, params={
            "keyword": "FullStack Dev Combined",
            "location": "Da Nang",
            "employment_type": "FULL_TIME",
            "experience_level": "MID",
        })
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(job.id) in ids
    finally:
        _delete_job(job.id)


def test_candidate_discovery_filters_and_search_param():
    job = _create_job(
        title="Candidate Discovery Backend Unique",
        company_name="Candidate Discovery Company",
        location="Ha Noi",
        industry=Industry.INFORMATION_TECHNOLOGY,
        experience_requirement=ExperienceRequirement.ONE_TO_THREE_YEARS,
        level=JobLevel.JUNIOR,
        work_mode=WorkMode.HYBRID,
        salary_min=20_000_000,
        salary_max=30_000_000,
        salary_type=SalaryType.RANGE,
    )
    try:
        resp = client.get(BASE, params={
            "search": "Candidate Discovery Backend Unique",
            "location": "Ha Noi",
            "industry": "INFORMATION_TECHNOLOGY",
            "experience_requirement": "ONE_TO_THREE_YEARS",
            "level": "JUNIOR",
            "work_mode": "HYBRID",
            "salary_min": 25_000_000,
            "salary_max": 25_000_000,
        })
        assert resp.status_code == 200, resp.text
        assert str(job.id) in [item["id"] for item in resp.json()["items"]]
    finally:
        _delete_job(job.id)


def test_negotiable_salary_filter():
    job = _create_job(
        title="Negotiable Salary Unique",
        salary_min=None,
        salary_max=None,
        salary_type=SalaryType.NEGOTIABLE,
    )
    try:
        resp = client.get(BASE, params={"search": "Negotiable Salary Unique", "salary_type": "NEGOTIABLE"})
        assert resp.status_code == 200, resp.text
        assert str(job.id) in [item["id"] for item in resp.json()["items"]]
    finally:
        _delete_job(job.id)


# ── Detail ────────────────────────────────────────────────────────────────────

def test_get_job_detail_200():
    job = _create_job(title="Detail Test Job", status=JobStatus.APPROVED)
    try:
        resp = client.get(f"{BASE}/{job.id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == str(job.id)
        assert data["title"] == "Detail Test Job"
        assert "password" not in data
        assert "password_hash" not in data
        assert "recruiter_id" not in data  # Not in public response schema
    finally:
        _delete_job(job.id)


def test_get_job_detail_returns_public_company_summary_from_owner_profile():
    db = _db()
    recruiter = User(
        email=f"public-company-{uuid.uuid4().hex}@example.com",
        password_hash="private-password-hash",
        full_name="Private Recruiter Name",
        phone="0901234567",
        role=UserRole.RECRUITER,
    )
    db.add(recruiter)
    db.flush()
    profile = RecruiterProfile(
        user_id=recruiter.id,
        company_name="GJob Technology",
        company_logo_url="https://cdn.example.com/gjob.png",
        company_description="Nền tảng tuyển dụng công nghệ.",
        company_website="https://gjob.example",
        industry="Công nghệ thông tin",
        company_address="Hà Nội",
        company_size=120,
    )
    db.add(profile)
    db.commit()
    recruiter_id = recruiter.id
    db.close()

    job = _create_job(
        title="Public Company Summary Job",
        company_name="Legacy Posting Name",
        recruiter_id=recruiter_id,
    )
    try:
        response = client.get(f"{BASE}/{job.id}")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == "Public Company Summary Job"
        assert data["company"] == {
            "name": "GJob Technology",
            "logo_url": "https://cdn.example.com/gjob.png",
            "description": "Nền tảng tuyển dụng công nghệ.",
            "website": "https://gjob.example",
            "industry": "Công nghệ thông tin",
            "address": "Hà Nội",
            "size": 120,
        }
        serialized = response.text
        assert "public-company-" not in serialized
        assert "0901234567" not in serialized
        assert "private-password-hash" not in serialized

        list_response = client.get(BASE, params={"search": "Public Company Summary Job"})
        assert list_response.status_code == 200
        assert "company" not in list_response.json()["items"][0]
    finally:
        _delete_job(job.id)
        cleanup_db = _db()
        cleanup_db.query(RecruiterProfile).filter(
            RecruiterProfile.user_id == recruiter_id
        ).delete()
        cleanup_db.query(User).filter(User.id == recruiter_id).delete()
        cleanup_db.commit()
        cleanup_db.close()


def test_get_job_detail_handles_missing_recruiter_profile():
    job = _create_job(title="Job Without Recruiter Profile")
    try:
        response = client.get(f"{BASE}/{job.id}")
        assert response.status_code == 200, response.text
        assert response.json()["company"] is None
        assert response.json()["company_name"] == "Test Corp"
    finally:
        _delete_job(job.id)


def test_get_job_detail_404():
    fake_id = uuid.uuid4()
    resp = client.get(f"{BASE}/{fake_id}")
    assert resp.status_code == 404


def test_pending_job_returns_404_on_detail():
    job = _create_job(title="Pending Detail Test", status=JobStatus.PENDING)
    try:
        resp = client.get(f"{BASE}/{job.id}")
        assert resp.status_code == 404, "PENDING job must not be accessible via detail endpoint"
    finally:
        _delete_job(job.id)


def test_rejected_job_returns_404_on_detail():
    job = _create_job(title="Rejected Detail Test", status=JobStatus.REJECTED)
    try:
        resp = client.get(f"{BASE}/{job.id}")
        assert resp.status_code == 404, "REJECTED job must not be accessible via detail endpoint"
    finally:
        _delete_job(job.id)


# ── Pagination metadata ───────────────────────────────────────────────────────

def test_pagination_metadata_correct():
    """Create 3 approved jobs and verify total/total_pages when page_size=2."""
    jobs = [_create_job(title=f"PaginationTest Job {i}", status=JobStatus.APPROVED) for i in range(3)]
    try:
        resp = client.get(BASE, params={"keyword": "PaginationTest Job", "page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert data["total_pages"] >= 2
        assert len(data["items"]) <= 2
    finally:
        for j in jobs:
            _delete_job(j.id)


# ── Sort ──────────────────────────────────────────────────────────────────────

def test_sort_newest_default():
    resp = client.get(BASE, params={"sort": "newest"})
    assert resp.status_code == 200


def test_sort_salary_high():
    resp = client.get(BASE, params={"sort": "salary_high"})
    assert resp.status_code == 200


def test_invalid_sort_422():
    resp = client.get(BASE, params={"sort": "invalid_sort_option"})
    assert resp.status_code == 422


# ── Regression: Task 02 / 03 ──────────────────────────────────────────────────

def test_regression_register():
    email = f"reg_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "Reg User",
    })
    assert resp.status_code == 201, resp.text


def test_regression_login():
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "Login User",
    })
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_regression_users_me():
    email = f"me_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "Me User",
    })
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    token = login.json()["access_token"]
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email
