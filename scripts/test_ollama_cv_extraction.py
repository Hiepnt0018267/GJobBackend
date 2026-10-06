"""Manual, non-persistent smoke test for local Qwen CV extraction."""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai.ollama_provider import OllamaProvider
from app.core.config import settings
from app.services.cv_structured_extraction_service import (
    CVStructuredExtractionService,
)


CASES = (
    (
        "short_vi",
        """Nguyễn Minh An
Email: an.nguyen@example.com | Điện thoại: 0901002003
Mục tiêu: Phát triển hệ thống backend ổn định.
Kinh nghiệm: Backend Developer tại Công ty Sao Việt, 2023 - nay.
Kỹ năng: Python, FastAPI, PostgreSQL.
Học vấn: Đại học Bách khoa Hà Nội, Công nghệ thông tin, 2019 - 2023.
Ngoại ngữ: Tiếng Anh - B2.""",
        ("Nguyễn Minh An", "Python", "FastAPI"),
    ),
    (
        "long_vi",
        """Trần Thu Hà
Email: ha.tran@example.com | Điện thoại: 0911222333
Mục tiêu nghề nghiệp: Trở thành kỹ sư dữ liệu xây dựng nền tảng phân tích tin cậy.
Kinh nghiệm:
- Data Engineer, Công ty Dữ liệu Việt, 01/2022 - hiện tại. Xây dựng pipeline ETL bằng Python và Airflow; tối ưu PostgreSQL; triển khai Docker.
- Software Engineer, Công ty Ánh Dương, 06/2019 - 12/2021. Phát triển REST API với FastAPI; viết kiểm thử tự động; vận hành dịch vụ Linux.
Dự án:
- Nền tảng phân tích tuyển dụng: Python, Airflow, PostgreSQL, Docker. Thiết kế pipeline đồng bộ dữ liệu và dashboard nội bộ.
- Kho dữ liệu khách hàng: dbt, SQL, MinIO. Chuẩn hóa dữ liệu và kiểm soát chất lượng.
Học vấn: Đại học Công nghệ, Khoa học máy tính, 2015 - 2019.
Chứng chỉ: AWS Certified Cloud Practitioner, 2023.
Kỹ năng: Python, FastAPI, Airflow, PostgreSQL, Docker, SQL, Git, Linux, dbt.
Ngoại ngữ: Tiếng Anh - IELTS 7.0; Tiếng Nhật - N3.
Hoạt động bổ sung: Hướng dẫn hai kỹ sư mới, viết tài liệu kỹ thuật và phối hợp cùng nhóm sản phẩm.""",
        ("Trần Thu Hà", "Airflow", "PostgreSQL"),
    ),
    (
        "bilingual",
        """Lê Hoàng Nam / Leo Nam
Email: leo.nam@example.com | Phone: 0988777666
Career objective / Mục tiêu: Build reliable cloud-native products for Vietnamese users.
Experience / Kinh nghiệm: Full-stack Engineer at Blue Ocean, 2021 - Present. Built React interfaces and FastAPI services; deployed on AWS.
Education / Học vấn: University of Information Technology, Software Engineering, 2017 - 2021.
Skills / Kỹ năng: TypeScript, React, Python, FastAPI, AWS, Docker.
Project / Dự án: GJob recruitment platform - React, TypeScript, FastAPI.
Language / Ngoại ngữ: Vietnamese - Native; English - Professional working proficiency.""",
        ("Lê Hoàng Nam", "React", "FastAPI"),
    ),
)


async def main() -> None:
    provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_llm_model,
        timeout_seconds=settings.ollama_llm_timeout_seconds,
        num_ctx=settings.ollama_llm_num_ctx,
    )
    service = CVStructuredExtractionService(provider=provider)

    for name, text, expected_terms in CASES:
        result = await service.extract_from_text(text)
        searchable = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        extracted_skills = {skill.name.casefold() for skill in result.skills}
        metrics = asdict(provider.last_metrics) if provider.last_metrics else {}
        print(
            json.dumps(
                {
                    "case": name,
                    "schema_valid": True,
                    "expected_terms_found": {
                        term: term.casefold() in searchable.casefold()
                        for term in expected_terms
                    },
                    "quality_checks": {
                        "name_found": expected_terms[0].casefold()
                        in (result.personal_info.full_name or "").casefold(),
                        "explicit_skills_found": all(
                            term.casefold() in extracted_skills
                            for term in expected_terms[1:]
                        ),
                        "education_present": len(result.educations) > 0,
                        "experience_present": len(result.experiences) > 0,
                    },
                    "section_counts": {
                        "educations": len(result.educations),
                        "experiences": len(result.experiences),
                        "skills": len(result.skills),
                        "projects": len(result.projects),
                        "certificates": len(result.certificates),
                        "languages": len(result.languages),
                    },
                    "metrics": metrics,
                },
                ensure_ascii=True,
            ),
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
