"""Pure, deterministic and explainable baseline matching engine."""

from app.schemas.matching import (
    BaselineMatchComponents,
    BaselineMatchResult,
    CanonicalCVMatchingInput,
    CanonicalJobMatchingInput,
    MatchExplanation,
    MatchExplanationCode,
    MatchedSkillEvidence,
    SkillEvidenceSource,
    SkillMatchComponent,
)


BASELINE_MATCHING_VERSION = "baseline-v1"
BASELINE_SKILL_WEIGHT = 1.0
BASELINE_SCORE_DECIMALS = 2


class InsufficientMatchingSignalsError(RuntimeError):
    """Raised instead of fabricating a score when no component is evaluable."""


class BaselineMatchingEngine:
    """Measure explicit structured skill coverage without DB or external calls."""

    def match(
        self,
        cv: CanonicalCVMatchingInput,
        job: CanonicalJobMatchingInput,
    ) -> BaselineMatchResult:
        job_skills = {skill.normalized_name: skill for skill in job.skills}
        if not job_skills:
            raise InsufficientMatchingSignalsError(
                "The job has no structured skills available for baseline matching."
            )

        candidate_evidence: dict[str, set[SkillEvidenceSource]] = {}
        for skill in cv.skills:
            candidate_evidence.setdefault(skill.normalized_name, set()).add(
                SkillEvidenceSource.CV_SKILL
            )
        for project in cv.projects:
            for technology in project.technologies:
                candidate_evidence.setdefault(
                    technology.normalized_name, set()
                ).add(SkillEvidenceSource.PROJECT_TECHNOLOGY)

        ordered_names = sorted(job_skills)
        matched_names = [
            name for name in ordered_names if name in candidate_evidence
        ]
        missing_names = [
            name for name in ordered_names if name not in candidate_evidence
        ]
        score = round(
            len(matched_names) / len(ordered_names) * 100,
            BASELINE_SCORE_DECIMALS,
        )

        matched_skills = [job_skills[name].name for name in matched_names]
        missing_skills = [job_skills[name].name for name in missing_names]
        evidence = [
            MatchedSkillEvidence(
                skill=job_skills[name].name,
                normalized_name=name,
                sources=sorted(candidate_evidence[name], key=lambda source: source.value),
            )
            for name in matched_names
        ]
        component = SkillMatchComponent(
            available=True,
            score=score,
            configured_weight=BASELINE_SKILL_WEIGHT,
            effective_weight=1.0,
            job_skills=[job_skills[name].name for name in ordered_names],
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            evidence=evidence,
        )
        strengths = []
        if matched_skills:
            strengths.append(
                MatchExplanation(
                    code=MatchExplanationCode.SKILL_COVERAGE,
                    message=(
                        f"CV thể hiện {len(matched_skills)}/{len(ordered_names)} "
                        "kỹ năng được tin tuyển dụng liệt kê."
                    ),
                    evidence=matched_skills,
                )
            )
        gaps = [
            MatchExplanation(
                code=MatchExplanationCode.SKILL_NOT_FOUND_IN_CV,
                message=f"Không tìm thấy {skill} trong dữ liệu CV.",
                evidence=[skill],
            )
            for skill in missing_skills
        ]
        return BaselineMatchResult(
            algorithm_version=BASELINE_MATCHING_VERSION,
            cv_id=cv.cv_id,
            job_id=job.job_id,
            overall_score=score,
            components=BaselineMatchComponents(skills=component),
            strengths=strengths,
            gaps=gaps,
        )
