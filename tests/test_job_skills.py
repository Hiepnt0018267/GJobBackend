"""Skill-taxonomy integration and database-integrity tests."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.main import app
from app.models.job import Job, JobStatus
from app.models.skill import JobSkill, Skill, normalize_skill_name


client = TestClient(app)


def _approved_job(skills: list[str]) -> uuid.UUID:
    db = SessionLocal()
    try:
        job = Job(
            title=f"Skill taxonomy {uuid.uuid4().hex}",
            description="Skill taxonomy regression test",
            company_name="GJob",
            skills=skills,
            status=JobStatus.APPROVED,
        )
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


def test_job_skill_projection_normalizes_duplicates_and_replaces_links() -> None:
    job_id = _approved_job([" Python ", "PYTHON", "Java", "JavaScript"])
    db = SessionLocal()
    try:
        links = (
            db.query(Skill.normalized_name)
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .filter(JobSkill.job_id == job_id)
            .order_by(Skill.normalized_name)
            .all()
        )
        assert [name for (name,) in links] == ["java", "javascript", "python"]

        job = db.get(Job, job_id)
        assert job is not None
        job.skills = [" FastAPI ", "fastapi"]
        db.commit()

        replaced = (
            db.query(Skill.normalized_name)
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .filter(JobSkill.job_id == job_id)
            .all()
        )
        assert replaced == [("fastapi",)]
    finally:
        db.close()


def test_public_job_filter_uses_exact_normalized_skill() -> None:
    marker = uuid.uuid4().hex[:12]
    skill_name = f"Skill {marker}"
    matching_job_id = _approved_job([skill_name, "Python"])
    _approved_job([f"{skill_name} extended"])

    response = client.get("/api/v1/jobs", params={"skill": f"  {skill_name.upper()}  "})

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert str(matching_job_id) in ids
    assert all(
        normalize_skill_name(skill_name) in {
            normalize_skill_name(skill) for skill in item["skills"]
        }
        for item in response.json()["items"]
    )


def test_skill_and_job_link_uniqueness_are_enforced() -> None:
    job_id = _approved_job([f"Unique {uuid.uuid4().hex}"])
    db = SessionLocal()
    try:
        link = db.query(JobSkill).filter(JobSkill.job_id == job_id).one()
        skill = db.get(Skill, link.skill_id)
        assert skill is not None

        db.add(
            Skill(
                name=skill.name.upper(),
                normalized_name=skill.normalized_name,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        skill_id = link.skill_id
        db.expunge_all()
        db.add(JobSkill(job_id=job_id, skill_id=skill_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_deleting_job_cascades_links_but_preserves_taxonomy() -> None:
    job_id = _approved_job([f"Cascade {uuid.uuid4().hex}"])
    db = SessionLocal()
    try:
        link = db.query(JobSkill).filter(JobSkill.job_id == job_id).one()
        skill_id = link.skill_id
        job = db.get(Job, job_id)
        assert job is not None
        db.delete(job)
        db.commit()

        assert db.query(JobSkill).filter(JobSkill.job_id == job_id).count() == 0
        assert db.get(Skill, skill_id) is not None
    finally:
        db.close()
