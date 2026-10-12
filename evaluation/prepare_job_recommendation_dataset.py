"""Create the frozen, synthetic Task 15B candidate-job evaluation dataset once."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.models.job import (
    EmploymentType,
    ExperienceLevel,
    ExperienceRequirement,
    Industry,
    JobLevel,
    JobStatus,
    SalaryType,
    WorkMode,
)
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job
from app.services.matching_input_mapper import build_cv_matching_input, build_job_matching_input
from app.services.matching_text_privacy import MATCHING_CANONICAL_VERSION


DATASET_VERSION = "job-recommendation-v1"
SCHEMA_VERSION = "job-recommendation-evaluation-schema-v1"
CREATED_AT = "2026-10-11T00:00:00+07:00"
SEED = 42
LABEL_FIELDS = (
    "candidate_id",
    "job_id",
    "relevance",
    "hard_negative_family",
    "rationale",
)


def _uuid(namespace: int, index: int) -> uuid.UUID:
    return uuid.UUID(f"{namespace:08x}-0000-0000-0000-{index:012d}")


CANDIDATES = [
    {
        "key": "python_backend",
        "archetype": "Python/FastAPI backend",
        "objective": "Backend engineer building reliable APIs and PostgreSQL services.",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Pytest"],
        "position": "Backend Engineer",
        "experience": "Built REST APIs, database services, automated tests, and containerized deployments.",
        "projects": [("API platform", "Backend developer", "Designed FastAPI services and PostgreSQL data models.", ["Python", "FastAPI", "PostgreSQL"])],
        "applied": 26,
    },
    {
        "key": "java_backend",
        "archetype": "Java/Spring backend",
        "objective": "Java backend engineer focused on Spring Boot services and relational data.",
        "skills": ["Java", "Spring Boot", "PostgreSQL", "JUnit", "Docker"],
        "position": "Java Backend Engineer",
        "experience": "Developed Spring Boot microservices, database integrations, and automated tests.",
        "projects": [("Order service", "Backend developer", "Implemented Java APIs with Spring Boot and PostgreSQL.", ["Java", "Spring Boot", "PostgreSQL"])],
        "applied": 28,
    },
    {
        "key": "react_frontend",
        "archetype": "React frontend",
        "objective": "Frontend engineer creating accessible React and TypeScript product interfaces.",
        "skills": ["React", "TypeScript", "JavaScript", "HTML", "CSS"],
        "position": "Frontend Engineer",
        "experience": "Built responsive React interfaces, reusable components, and browser tests.",
        "projects": [("Product dashboard", "Frontend developer", "Created a React TypeScript dashboard with accessible components.", ["React", "TypeScript", "CSS"])],
        "applied": 25,
    },
    {
        "key": "fullstack",
        "archetype": "Full-stack React/Node",
        "objective": "Full-stack engineer delivering React clients and Node API services.",
        "skills": ["React", "TypeScript", "Node.js", "NestJS", "PostgreSQL"],
        "position": "Full-stack Engineer",
        "experience": "Owned frontend workflows and backend APIs for a web product.",
        "projects": [("Commerce application", "Full-stack developer", "Built React screens and NestJS services backed by PostgreSQL.", ["React", "NestJS", "PostgreSQL"])],
        "applied": 22,
    },
    {
        "key": "data_analyst",
        "archetype": "Data Analyst",
        "objective": "Data analyst translating business questions into SQL analysis and dashboards.",
        "skills": ["SQL", "Power BI", "Excel", "Python", "Statistics"],
        "position": "Data Analyst",
        "experience": "Prepared analytical datasets, KPI reports, and stakeholder dashboards.",
        "projects": [("Revenue dashboard", "Analyst", "Modeled business metrics in SQL and Power BI.", ["SQL", "Power BI", "Excel"])],
        "applied": 28,
    },
    {
        "key": "data_engineer",
        "archetype": "Data Engineer",
        "objective": "Data engineer building dependable batch pipelines and warehouse models.",
        "skills": ["Python", "SQL", "Apache Spark", "Airflow", "Kafka"],
        "position": "Data Engineer",
        "experience": "Developed ETL pipelines, scheduled workflows, and distributed data processing jobs.",
        "projects": [("Lakehouse pipeline", "Data engineer", "Implemented Airflow pipelines and Spark transformations.", ["Python", "Airflow", "Apache Spark"])],
        "applied": 26,
    },
    {
        "key": "ml_engineer",
        "archetype": "ML/AI Engineer",
        "objective": "Machine learning engineer training models and shipping reproducible inference systems.",
        "skills": ["Python", "PyTorch", "scikit-learn", "MLflow", "Docker"],
        "position": "Machine Learning Engineer",
        "experience": "Trained predictive models, evaluated experiments, and deployed inference services.",
        "projects": [("Prediction service", "ML engineer", "Built a PyTorch training pipeline and containerized model service.", ["Python", "PyTorch", "MLflow"])],
        "applied": 27,
    },
    {
        "key": "qa_automation",
        "archetype": "QA Automation",
        "objective": "QA automation engineer improving release confidence through browser and API tests.",
        "skills": ["Selenium", "Playwright", "Python", "Pytest", "API Testing"],
        "position": "QA Automation Engineer",
        "experience": "Created automated regression suites for web interfaces and REST APIs.",
        "projects": [("Regression suite", "QA engineer", "Automated browser and API scenarios with Playwright and Pytest.", ["Playwright", "Python", "Pytest"])],
        "applied": 27,
    },
    {
        "key": "devops",
        "archetype": "DevOps/Cloud",
        "objective": "DevOps engineer operating cloud infrastructure and reliable delivery pipelines.",
        "skills": ["Kubernetes", "Terraform", "Docker", "AWS", "GitHub Actions"],
        "position": "DevOps Engineer",
        "experience": "Automated cloud infrastructure, CI/CD pipelines, monitoring, and Kubernetes operations.",
        "projects": [("Cloud platform", "DevOps engineer", "Provisioned AWS infrastructure with Terraform and operated Kubernetes workloads.", ["AWS", "Terraform", "Kubernetes"])],
        "applied": 28,
    },
    {
        "key": "mobile",
        "archetype": "Mobile Developer (sparse profile)",
        "objective": "Mobile developer building cross-platform applications.",
        "skills": ["Flutter", "Dart", "REST APIs"],
        "position": "Mobile Developer",
        "experience": "Implemented Flutter screens and integrated mobile applications with REST APIs.",
        "projects": [],
        "applied": 25,
    },
]


JOBS = [
    ("Python FastAPI Backend Engineer", "Build production APIs and PostgreSQL services with FastAPI, Docker, and Pytest.", ["Python", "FastAPI", "PostgreSQL", "Docker", "Pytest"]),
    ("Java Spring Backend Engineer", "Develop Spring Boot microservices and relational database integrations.", ["Java", "Spring Boot", "PostgreSQL", "JUnit"]),
    ("Node NestJS Backend Engineer", "Build TypeScript backend APIs using Node.js, NestJS, and PostgreSQL.", ["TypeScript", "Node.js", "NestJS", "PostgreSQL"]),
    ("React Frontend Engineer", "Create accessible web interfaces and reusable components with React and TypeScript.", ["React", "TypeScript", "HTML", "CSS"]),
    ("Full-stack React Node Engineer", "Deliver React product workflows and Node.js API services end to end.", ["React", "TypeScript", "Node.js", "PostgreSQL"]),
    ("Data Analyst", "Analyze business performance with SQL, Excel, statistics, and Power BI dashboards.", ["SQL", "Power BI", "Excel", "Statistics"]),
    ("Data Engineer", "Develop reliable Airflow pipelines, Spark transformations, and warehouse datasets.", ["Python", "SQL", "Airflow", "Apache Spark"]),
    ("Machine Learning Engineer", "Train and deploy machine learning models using Python, PyTorch, and MLflow.", ["Python", "PyTorch", "MLflow", "Docker"]),
    ("QA Automation Engineer", "Automate browser and API regression testing with Selenium, Playwright, and Pytest.", ["Selenium", "Playwright", "Python", "Pytest"]),
    ("DevOps Cloud Engineer", "Operate Kubernetes workloads and provision AWS infrastructure using Terraform.", ["Kubernetes", "Terraform", "AWS", "Docker"]),
    ("Android Java Developer", "Build native Android applications with Java, Kotlin, and Android SDK.", ["Java", "Kotlin", "Android SDK"]),
    ("Flutter Mobile Developer", "Build cross-platform mobile products with Flutter, Dart, and REST APIs.", ["Flutter", "Dart", "REST APIs"]),
    ("iOS Swift Developer", "Develop native iOS applications with Swift and UIKit.", ["Swift", "UIKit", "iOS"]),
    ("Python Data Scientist", "Explore datasets and build statistical machine learning models in Python.", ["Python", "pandas", "scikit-learn", "Statistics"]),
    ("Python Automation Specialist", "Write Python scripts to automate operational workflows and file processing.", ["Python", "Scripting", "Automation"]),
    ("Go Backend Engineer", "Develop concurrent backend APIs and distributed services using Go.", ["Go", "PostgreSQL", "Docker", "REST APIs"]),
    ("PHP Laravel Backend Engineer", "Build web APIs and business services with PHP and Laravel.", ["PHP", "Laravel", "MySQL"]),
    ("C Sharp .NET Backend Engineer", "Implement enterprise APIs with C#, ASP.NET Core, and SQL Server.", ["C#", "ASP.NET Core", "SQL Server"]),
    ("Vue Frontend Engineer", "Create responsive web applications with Vue, TypeScript, and CSS.", ["Vue", "TypeScript", "CSS"]),
    ("Angular Frontend Engineer", "Build enterprise web interfaces with Angular and TypeScript.", ["Angular", "TypeScript", "CSS"]),
    ("Site Reliability Engineer", "Improve cloud reliability through Kubernetes, observability, incident response, and infrastructure automation.", ["Kubernetes", "Terraform", "Monitoring", "AWS"]),
    ("Manual QA Engineer", "Design test cases, execute exploratory testing, and report product defects.", ["Manual Testing", "Test Cases", "Bug Tracking"]),
    ("Business Intelligence Engineer", "Model analytics data and deliver SQL and Tableau reporting layers.", ["SQL", "Tableau", "Data Modeling"]),
    ("MLOps Engineer", "Operate model training and serving platforms with MLflow, Docker, Kubernetes, and CI/CD.", ["MLflow", "Docker", "Kubernetes", "Python"]),
    ("Cybersecurity Analyst", "Monitor security events, investigate threats, and improve defensive controls.", ["SIEM", "Incident Response", "Network Security"]),
    ("Product Designer", "Design user flows, prototypes, and visual systems for digital products.", ["Figma", "Prototyping", "User Research"]),
    ("Technical Product Manager", "Define product outcomes, prioritize roadmaps, and coordinate engineering delivery.", ["Product Strategy", "Roadmapping", "Agile"]),
    ("Technical Support Specialist", "Resolve customer technical issues and maintain support documentation.", ["Troubleshooting", "Customer Support", "Documentation"]),
    ("Backend Developer", "Build APIs.", ["Python"]),
    ("Software Engineer", "Join a delivery team working across web services, cloud deployment, analytics, testing, and user interfaces.", ["Python", "Java", "React", "Docker", "SQL"]),
    ("Draft Python Engineer", "Draft role not approved for candidate discovery.", ["Python", "FastAPI"]),
    ("Closed React Engineer", "Closed role not available for candidate discovery.", ["React", "TypeScript"]),
]


GRADES = {
    "python_backend": [3,1,1,0,2,1,2,1,0,1,0,0,0,0,2,2,1,1,0,0,1,0,1,1,0,0,0,0,3,2],
    "java_backend": [1,3,1,0,2,0,1,0,0,1,0,0,0,0,1,2,1,2,0,0,1,0,0,0,0,0,0,0,2,2],
    "react_frontend": [0,0,0,3,3,0,0,0,1,0,0,0,0,0,1,0,0,0,2,2,0,0,0,0,0,1,0,0,1,2],
    "fullstack": [2,1,2,2,3,0,1,0,1,1,0,0,0,0,1,1,0,1,2,2,1,0,0,0,0,0,0,0,2,3],
    "data_analyst": [0,0,0,0,0,3,1,1,0,0,0,0,0,2,1,0,0,0,0,0,0,0,3,1,0,0,0,0,0,1],
    "data_engineer": [1,0,0,0,1,2,3,2,0,1,0,0,0,2,2,1,0,0,0,0,1,0,2,2,0,0,0,0,1,2],
    "ml_engineer": [0,0,0,0,0,1,2,3,0,1,0,0,0,3,0,0,0,0,0,0,1,0,1,2,0,0,0,0,0,2],
    "qa_automation": [0,0,1,1,1,0,0,0,3,0,0,0,0,0,2,0,0,0,0,0,0,2,0,0,0,0,0,0,1,2],
    "devops": [0,0,1,0,1,0,1,0,0,3,0,0,0,0,1,1,0,0,0,0,3,0,0,2,1,0,0,0,0,2],
    "mobile": [0,0,0,1,1,0,0,0,0,0,2,3,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
}


HARD_NEGATIVES = {
    ("python_backend", 14): "python_backend_vs_python_data_science",
    ("react_frontend", 3): "react_frontend_vs_node_backend",
    ("devops", 1): "devops_vs_backend_docker_kubernetes",
    ("java_backend", 11): "java_backend_vs_android_java",
    ("qa_automation", 1): "qa_automation_vs_backend_test_tooling",
    ("ml_engineer", 15): "ml_engineer_vs_python_scripting",
}


def _candidate_fixture(item: dict, index: int) -> dict:
    candidate_id = _uuid(0x15000000, index)
    cv_id = _uuid(0x15100000, index)
    source = SimpleNamespace(
        id=cv_id,
        personal_info={},
        career_objective=item["objective"],
        skills=[{"name": skill, "level": "ADVANCED"} for skill in item["skills"]],
        experiences=[{
            "company_name": "Synthetic Product Team",
            "position": item["position"],
            "description": item["experience"],
            "is_current": False,
        }],
        educations=[],
        projects=[{
            "name": name,
            "role": role,
            "description": description,
            "technologies": technologies,
        } for name, role, description, technologies in item["projects"]],
        certificates=[],
        languages=[],
    )
    canonical = build_cv_matching_input(source)
    return {
        "candidate_id": str(candidate_id),
        "archetype": item["archetype"],
        "applied_job_ids": [str(_uuid(0x15200000, item["applied"]))],
        "canonical_fingerprint": fingerprint_cv(canonical),
        "canonical": canonical.model_dump(mode="json"),
    }


def _job_fixture(index: int, title: str, description: str, skills: list[str]) -> dict:
    status = JobStatus.APPROVED
    if index == 31:
        status = JobStatus.PENDING
    elif index == 32:
        status = JobStatus.CLOSED
    job_id = _uuid(0x15200000, index)
    source = SimpleNamespace(
        id=job_id,
        title=title,
        description=description,
        requirements="Use the listed professional skills and collaborate with the delivery team.",
        skills=skills,
        location=None,
        industry=Industry.INFORMATION_TECHNOLOGY,
        employment_type=EmploymentType.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        level=JobLevel.STAFF,
        experience_requirement=ExperienceRequirement.ONE_TO_THREE_YEARS,
        work_mode=WorkMode.HYBRID,
        status=status,
        salary_type=SalaryType.NEGOTIABLE,
        salary_min=None,
        salary_max=None,
        salary_fixed=None,
        salary_currency="VND",
        vacancies=1,
    )
    canonical = build_job_matching_input(source)
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)
    controlled_status = {9: "pending", 17: "unavailable", 24: "error"}.get(index)
    return {
        "job_id": str(job_id),
        "archetype": title,
        "created_at": created_at.isoformat(),
        "controlled_signal_status": controlled_status,
        "canonical_fingerprint": fingerprint_job(canonical),
        "canonical": canonical.model_dump(mode="json"),
    }


def _rationale(grade: int, family: str) -> str:
    if family:
        return "Shared technology is misleading because the professional role differs."
    return {
        3: "Role, core stack, and professional context strongly align.",
        2: "The role is plausible with meaningful transferable overlap or limited gaps.",
        1: "Only peripheral professional adjacency is present.",
        0: "The role and professional context are unrelated.",
    }[grade]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(rows: list[dict]) -> str:
    payload = [
        {
            "id": row.get("candidate_id", row.get("job_id")),
            "canonical": row["canonical"],
        }
        for row in rows
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "candidates.jsonl": output / "candidates.jsonl",
        "jobs.jsonl": output / "jobs.jsonl",
        "labels.csv": output / "labels.csv",
        "manifest.json": output / "manifest.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Frozen dataset files already exist: {existing}")

    candidates = [_candidate_fixture(item, index) for index, item in enumerate(CANDIDATES, 1)]
    jobs = [_job_fixture(index, *definition) for index, definition in enumerate(JOBS, 1)]
    labels = []
    for candidate, definition in zip(candidates, CANDIDATES, strict=True):
        grades = GRADES[definition["key"]]
        if len(grades) != 30:
            raise ValueError("Each explicit relevance row must cover all approved fixture jobs.")
        applied = set(candidate["applied_job_ids"])
        for job_index, grade in enumerate(grades, 1):
            job_id = str(_uuid(0x15200000, job_index))
            if job_id in applied:
                continue
            family = HARD_NEGATIVES.get((definition["key"], job_index), "")
            labels.append({
                "candidate_id": candidate["candidate_id"],
                "job_id": job_id,
                "relevance": grade,
                "hard_negative_family": family,
                "rationale": _rationale(grade, family),
            })

    paths["candidates.jsonl"].write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in candidates),
        encoding="utf-8",
        newline="\n",
    )
    paths["jobs.jsonl"].write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in jobs),
        encoding="utf-8",
        newline="\n",
    )
    with paths["labels.csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(labels)

    controlled_candidate = candidates[7]["candidate_id"]
    manifest = {
        "dataset_version": DATASET_VERSION,
        "schema_version": SCHEMA_VERSION,
        "canonical_version": MATCHING_CANONICAL_VERSION,
        "candidate_count": len(candidates),
        "job_count": len(jobs),
        "approved_job_count": 30,
        "pair_count": len(labels),
        "relevance_schema": {
            "0": "irrelevant",
            "1": "weak or peripheral fit",
            "2": "plausible or moderate fit",
            "3": "strong fit",
            "binary_relevant": "relevance >= 2",
        },
        "created_at": CREATED_AT,
        "random_seed": SEED,
        "files": {name: {"sha256": _sha256(path)} for name, path in paths.items() if name != "manifest.json"},
        "canonical_content_sha256": {
            "candidates": _canonical_digest(candidates),
            "jobs": _canonical_digest(jobs),
        },
        "controlled_missingness": {
            "evidence_type": "diagnostic mask, not an observed BGE failure",
            "candidate_status": {controlled_candidate: "unavailable"},
            "job_status_by_candidate": {
                candidates[0]["candidate_id"]: {str(_uuid(0x15200000, 9)): "unavailable"},
                candidates[1]["candidate_id"]: {
                    str(_uuid(0x15200000, 17)): "pending",
                    str(_uuid(0x15200000, 24)): "unavailable",
                },
                candidates[3]["candidate_id"]: {str(_uuid(0x15200000, 24)): "error"},
            },
        },
    }
    paths["manifest.json"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/data/job-recommendation-v1"),
    )
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
