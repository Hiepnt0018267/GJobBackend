import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"
    FREELANCE = "FREELANCE"


class ExperienceLevel(str, enum.Enum):
    ENTRY = "ENTRY"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    MANAGER = "MANAGER"


class JobLevel(str, enum.Enum):
    INTERN = "INTERN"
    JUNIOR = "JUNIOR"
    STAFF = "STAFF"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    MANAGER = "MANAGER"


class ExperienceRequirement(str, enum.Enum):
    NO_EXPERIENCE = "NO_EXPERIENCE"
    LESS_THAN_ONE_YEAR = "LESS_THAN_ONE_YEAR"
    ONE_TO_THREE_YEARS = "ONE_TO_THREE_YEARS"
    THREE_TO_FIVE_YEARS = "THREE_TO_FIVE_YEARS"
    MORE_THAN_FIVE_YEARS = "MORE_THAN_FIVE_YEARS"


class WorkMode(str, enum.Enum):
    ONSITE = "ONSITE"
    HYBRID = "HYBRID"
    REMOTE = "REMOTE"


class SalaryType(str, enum.Enum):
    RANGE = "RANGE"
    FIXED = "FIXED"
    NEGOTIABLE = "NEGOTIABLE"


class Industry(str, enum.Enum):
    INFORMATION_TECHNOLOGY = "INFORMATION_TECHNOLOGY"
    FINANCE_BANKING = "FINANCE_BANKING"
    MARKETING_ADVERTISING = "MARKETING_ADVERTISING"
    SALES = "SALES"
    HUMAN_RESOURCES = "HUMAN_RESOURCES"
    EDUCATION = "EDUCATION"
    HEALTHCARE = "HEALTHCARE"
    MANUFACTURING = "MANUFACTURING"
    LOGISTICS = "LOGISTICS"
    OTHER = "OTHER"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    # Recruiter who posted the job (FK to users.id, nullable so seeds/tests are easy)
    recruiter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_type: Mapped[Optional[SalaryType]] = mapped_column(
        Enum(SalaryType, name="salarytype"), nullable=True
    )
    salary_fixed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="VND", server_default="VND"
    )

    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(
        Enum(EmploymentType, name="employmenttype"), nullable=True, index=True
    )
    experience_level: Mapped[Optional[ExperienceLevel]] = mapped_column(
        Enum(ExperienceLevel, name="experiencelevel"), nullable=True, index=True
    )
    level: Mapped[Optional[JobLevel]] = mapped_column(
        Enum(JobLevel, name="joblevel"), nullable=True, index=True
    )
    experience_requirement: Mapped[Optional[ExperienceRequirement]] = mapped_column(
        Enum(ExperienceRequirement, name="experiencerequirement"), nullable=True
    )
    work_mode: Mapped[Optional[WorkMode]] = mapped_column(
        Enum(WorkMode, name="workmode"), nullable=True
    )
    industry: Mapped[Optional[Industry]] = mapped_column(
        Enum(Industry, name="industry"), nullable=True, index=True
    )
    vacancies: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    benefits: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # skills stored as a PostgreSQL text array e.g. ["Python", "FastAPI"]
    skills: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"),
        nullable=False,
        default=JobStatus.PENDING,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    skill_links: Mapped[List["JobSkill"]] = relationship(
        back_populates="job", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title!r} status={self.status}>"
