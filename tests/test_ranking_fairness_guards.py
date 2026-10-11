"""14C.4 synthetic invariance and risk-observation tests, never model inference."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS
from uuid import UUID

import pytest

from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.recruiter_application import RecruiterApplicationListItem
from app.services.matching_input_mapper import build_cv_matching_input, build_job_matching_input
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job
from app.services.matching_text_privacy import find_matching_text_privacy_issues
from app.services.semantic_matching_service import SemanticMatchingService
from app.embeddings.base import EmbeddingBatchResult
from evaluation.audit_ranking_fairness import cohort_metrics, text_inventory


def payload():
    return {"personal_info": {}, "career_objective": "Build reliable Python APIs",
        "experiences": [{"company_name":"SYNTHETIC EMPLOYER", "position":"Engineer",
                         "description":"Develop reliable APIs"}],
        "educations": [{"school_name":"SYNTHETIC SCHOOL", "degree":"Engineering"}],
        "skills": [{"name":"Python"}], "projects":[{"name":"API Project"}],
        "certificates":[{"name":"API Certification"}],
        "languages":[{"name":"English", "proficiency":"FLUENT"}]}


def canonical(value, key=1):
    return build_cv_matching_input(NS(id=UUID(int=key)), StructuredCVExtractionResult.model_validate(value))


@pytest.mark.parametrize("identity", [
    {"full_name":"Synthetic Name"}, {"email":"synthetic@example.com"},
    {"phone":"0912345678"}, {"address":"Synthetic private street"},
    {"avatar_url":"https://example.test/photo.png"}, {"date_of_birth":"1990-01-01"},
    {"linkedin_url":"https://linkedin.com/in/synthetic"},
])
def test_direct_identity_changes_neither_text_nor_fingerprint(identity):
    before = payload(); changed=deepcopy(before); changed["personal_info"]=identity
    a, b = canonical(before), canonical(changed, 2)
    assert a.semantic_text == b.semantic_text
    assert fingerprint_cv(a) == fingerprint_cv(b)
    if "address" in identity:
        assert a.location is None and b.location is not None  # metadata != embedding feature
    assert changed["personal_info"] == identity


def test_professional_metadata_dates_and_photo_paths_not_semantic_features():
    original = payload(); changed=deepcopy(original)
    changed["experiences"][0].update(company_name="OTHER EMPLOYER",start_date="2020",end_date="2023")
    changed["educations"][0].update(school_name="OTHER SCHOOL",start_date="2010",end_date="2014")
    a,b = canonical(original),canonical(changed)
    assert a.semantic_text == b.semantic_text and fingerprint_cv(a)==fingerprint_cv(b)
    assert "OTHER EMPLOYER" not in b.semantic_text and "OTHER SCHOOL" not in b.semantic_text
    # Extra ORM account/photo metadata is not serialized by the mapper.
    carrier=NS(id=UUID(int=1),**original,photo_storage_key="private/photo.webp",candidate_id=UUID(int=44),
               gender="synthetic protected value", nationality="synthetic protected value")
    assert build_cv_matching_input(carrier).semantic_text==a.semantic_text


def test_free_prose_risk_survives_without_inferring_demographics():
    value=payload()
    value["career_objective"]="She develops APIs. Home address: Synthetic private street. Graduated 2010."
    text=canonical(value).semantic_text
    assert "She develops" in text and "Synthetic private street" in text and "2010" in text
    # Contact auditor is NOT an address/name/pronoun/protected-attribute detector.
    assert find_matching_text_privacy_issues(text)==()
    counts=text_inventory([{"status":"SUCCEEDED","canonical_input":canonical(value).model_dump(mode="json")}],"cv")
    assert counts["document_cue_counts_not_group_labels"]["gendered_pronoun_terms"]==1
    assert counts["document_cue_counts_not_group_labels"]["address_label"]==1
    assert "Synthetic private street" not in str(counts)


def test_supported_prose_contacts_sanitized_by_exact_production_mapper():
    value=payload(); value["career_objective"]="APIs; Email: synthetic@example.test; Phone: +84 912 345 678"
    text=canonical(value).semantic_text
    assert "synthetic@example.test" not in text and "+84 912" not in text
    assert "[CONTACT]" in text and find_matching_text_privacy_issues(text)==()


def test_jd_location_company_account_metadata_excluded_from_semantic_input():
    from test_applicant_ranking import applicants
    job=applicants(1)[0].job
    first=build_job_matching_input(job)
    job.location="Synthetic city"; job.company_name="Changed company"
    job.recruiter_id=UUID(int=90); job.id=UUID(int=91)
    second=build_job_matching_input(job)
    assert first.semantic_text==second.semantic_text and fingerprint_job(first)==fingerprint_job(second)
    assert second.location is not None


def test_builder_uploaded_gap_is_technical_not_demographic(monkeypatch):
    from app.models.cv import CVSourceType
    from app.services.matching_input_service import MatchingInputService, CVNotReadyForMatchingError
    from app.services.applicant_ranking_service import ApplicantRankingService
    from app.services.ranking_cache import RankingCache
    class Query:
        def filter(self,*a): return self
        def order_by(self,*a): return self
        def all(self): return []
    db=NS(query=lambda *a:Query())
    builder=NS(id=UUID(int=1),source_type=CVSourceType.BUILDER,**payload())
    uploaded=NS(id=UUID(int=2),source_type=CVSourceType.UPLOADED,**payload())
    values=MatchingInputService(db).build_cv_inputs([builder,uploaded])
    assert not isinstance(values[builder.id],Exception)
    assert isinstance(values[uploaded.id],CVNotReadyForMatchingError)
    # A cold but canonical-ready Builder is PENDING; uploaded without a persisted
    # extraction is UNAVAILABLE even if arbitrary structured-like fields exist.
    cache=RankingCache("unused-synthetic-path")
    monkeypatch.setattr(cache,"vector",lambda *a:("pending",None))
    service=ApplicantRankingService(db,cache)
    assert service._vector("cv",values[builder.id])==("pending",None)
    assert service._vector("cv",values[uploaded.id])==("unavailable",None)


def test_identity_equal_text_produces_identical_mock_score_without_live_model():
    from test_applicant_ranking import applicants
    class MockTextProvider:
        def __init__(self): self.seen=[]
        async def embed_many(self,texts):
            self.seen.append(tuple(texts))
            return EmbeddingBatchResult(vectors=((1.,0.),(.8,.6)), provider="mock", model="mock", dimensions=2)
    a=canonical(payload()); changed=payload();changed["personal_info"]={"full_name":"Another identity"}
    b=canonical(changed,2); job=build_job_matching_input(applicants(1)[0].job)
    provider=MockTextProvider(); service=SemanticMatchingService(provider)
    first=asyncio.run(service.match(a,job)); second=asyncio.run(service.match(b,job))
    assert provider.seen[0]==provider.seen[1] and first.semantic_similarity==second.semantic_similarity


@pytest.mark.parametrize("signals", [{1:.8,2:.8,3:.8}, {1:"pending",2:"unavailable",3:"error"}])
def test_identity_changes_neither_ties_nor_fallback_order(tmp_path,monkeypatch,signals):
    from test_applicant_ranking import applicants, service, listing
    rows=applicants(3); s=service(tmp_path,rows,signals,monkeypatch)
    before=listing(s,rows)
    for i,a in enumerate(rows):
        a.candidate=NS(id=a.candidate_id,full_name=f"Changed Identity {i}",email=f"changed{i}@example.test",
                       avatar_url="https://example.test/synthetic.png")
        a.cv.photo_storage_key="private/synthetic.webp"
    after=listing(s,rows)
    assert [r.id for r in before.items]==[r.id for r in after.items]
    assert [r.semantic_match_score for r in before.items]==[r.semantic_match_score for r in after.items]
    # Business-neutral tie/fallback field changes must change the documented default order.
    rows[0].created_at,rows[2].created_at=rows[2].created_at,rows[0].created_at
    rows.sort(key=lambda a:(a.created_at,a.id),reverse=True)
    changed=listing(s,rows)
    assert [r.id for r in changed.items]==[rows[0].id,rows[1].id,rows[2].id]
    assert [r.id for r in changed.items] != [r.id for r in before.items]


def test_ai_response_has_no_demographic_inference_fields():
    ai_keys={key for key in RecruiterApplicationListItem.model_fields if key.startswith(('ai_','ranking_','semantic_'))}
    assert ai_keys=={"ai_rank","ranking_status","semantic_match_score"}
    assert not {"gender","race","ethnicity","nationality","fairness_score","demographic_group"} & set(RecruiterApplicationListItem.model_fields)


def test_cohort_denominators_missing_rates_and_small_groups_not_hidden():
    rows=[{"pair_id":str(i),"cv_id":str(i),"job_id":"one","rank":str(i),
           "semantic_score":"0.5","relevance_grade":"1"} for i in range(1,7)]
    result=cohort_metrics(rows,{str(i):"Large" if i<6 else "Tiny" for i in range(1,7)})
    large,tiny=result
    assert large["n_candidate_job_rows"]==5 and large["size_guard"]=="HIGH_UNCERTAINTY_N_LT_10"
    assert tiny["n_candidate_job_rows"]==1 and tiny["size_guard"]=="DESCRIPTIVE_ONLY_N_LT_5"
    assert large["top3_rate"]==3/5 and tiny["mean_within_job_rank"]==6
    assert all(r["production_ranked_rate"] is None and r["production_pending_rate"] is None for r in result)
    with pytest.raises(ValueError,match="Missing source category"):
        cohort_metrics(rows,{})
    with pytest.raises(ValueError,match="Duplicate prediction"):
        cohort_metrics(rows+[rows[0]],{str(i):"A" for i in range(1,7)})
