"""Pure synthetic production-ranking tests (also runnable with --noconftest)."""
import asyncio
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.embeddings.base import EmbeddingBatchResult
from app.models.application import JobApplicationStatus
from app.models.cv import CVSourceType
from app.models.job import JobStatus
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.matching import CanonicalCVMatchingInput
from app.services.applicant_ranking_service import ApplicantRankingService
from app.services.matching_input_mapper import build_cv_matching_input
from app.services.matching_input_service import MatchingInputService, CVNotReadyForMatchingError
from app.services.ranking_cache import RankingCache, digest, entity_identity


def cv(i=1, text="Python"):
    return CanonicalCVMatchingInput(cv_id=UUID(int=i), semantic_text=text, skills=[],
        experiences=[], educations=[], projects=[], certificates=[], languages=[])


def applicants(count=17):
    now = datetime.now(timezone.utc)
    job = NS(id=UUID(int=1000), title="Backend", description="Python APIs", requirements=None,
        skills=[], skill_links=[], location=None, industry=None, employment_type=None,
        experience_level=None, level=None, experience_requirement=None, work_mode=None,
        status=JobStatus.APPROVED, salary_type=None, salary_min=None, salary_max=None,
        salary_fixed=None, salary_currency="USD", vacancies=1, company_name="Company")
    candidate = NS(id=UUID(int=2000), full_name="Display only", email="display@example.test", avatar_url=None)
    rows = []
    for i in range(count):
        c = NS(id=UUID(int=i+1), candidate_id=candidate.id, title="CV", source_type=CVSourceType.BUILDER,
            template=None, original_filename=None, mime_type=None, file_size=None, uploaded_at=None)
        rows.append(NS(id=UUID(int=i+3000), created_at=now-timedelta(seconds=i), updated_at=now,
            status=JobApplicationStatus.SUBMITTED, cv=c, cv_id=c.id, job=job, job_id=job.id,
            candidate=candidate, candidate_id=candidate.id))
    return rows


class FakeCache(RankingCache):
    def __init__(self, root, signals):
        super().__init__(root)
        self.signals = signals
        self.lookups = 0

    def vector(self, kind, canonical):
        self.lookups += 1
        if kind == "job":
            return "ranked", [1., 0.]
        value = self.signals.get(canonical.cv_id.int, "pending")
        if isinstance(value, str):
            return value, None
        return "ranked", [value, (1-value**2)**.5]


def service(tmp_path, rows, signals, monkeypatch):
    s = ApplicantRankingService(None, FakeCache(tmp_path, signals))
    monkeypatch.setattr(s.inputs, "build_cv_inputs", lambda values: {v.id: cv(v.id.int) for v in values})
    return s


def listing(s, rows, **kwargs):
    return s.list(rows, owner=UUID(int=9), filters=[None, None, None],
        page=kwargs.pop("page", 1), page_size=kwargs.pop("page_size", 20), **kwargs)


def test_scores_full_set_no_threshold_and_deterministic_tie(tmp_path, monkeypatch):
    rows = applicants()
    signals = {i+1: value for i, value in enumerate([.8, .6, .7, .4, .05, -.2, 0., .8])}
    s = service(tmp_path, rows, signals, monkeypatch)
    result = listing(s, rows)
    assert result.total == 17 and len(result.items) == 17
    assert [i.cv_id.int for i in result.items[:4]] == [1, 8, 3, 2]
    assert result.items[6].semantic_match_score == 0.
    assert result.items[7].semantic_match_score < 0
    assert all(i.semantic_match_score is None for i in result.items[8:])
    assert all(i.status == JobApplicationStatus.SUBMITTED for i in result.items)
    assert [i.id for i in listing(s, rows).items] == [i.id for i in result.items]


def test_global_pagination_snapshot_freezes_availability(tmp_path, monkeypatch):
    rows = applicants()
    s = service(tmp_path, rows, {1: .6, 17: .9}, monkeypatch)
    first = listing(s, rows, page_size=5)
    assert first.items[0].cv_id.int == 17  # originally outside DB page one
    old_order = listing(s, rows, page_size=5, snapshot=first.ranking_snapshot).items
    s.cache.signals[10] = .99
    seen = [i.id for i in old_order]
    lookups = s.cache.lookups
    for page in (2, 3, 4):
        result = listing(s, rows, page=page, page_size=5, snapshot=first.ranking_snapshot)
        seen.extend(i.id for i in result.items)
    assert len(seen) == len(set(seen)) == 17
    assert s.cache.lookups == lookups  # continuation never reevaluates availability
    assert listing(s, rows).items[0].cv_id.int == 10  # new traversal observes new signal


@pytest.mark.parametrize("change", ["membership", "status", "source", "profile", "owner"])
def test_snapshot_rejects_changed_context(tmp_path, monkeypatch, change):
    rows = applicants(3)
    s = service(tmp_path, rows, {1: .8}, monkeypatch)
    first = listing(s, rows, page_size=2)
    if change == "membership": rows.pop()
    elif change == "status": rows[0].status = JobApplicationStatus.REVIEWING
    elif change == "source": monkeypatch.setattr(s.inputs, "build_cv_inputs", lambda values: {v.id: cv(v.id.int, "Java") for v in values})
    elif change == "profile": monkeypatch.setattr(settings, "embedding_num_batch", 2048)
    with pytest.raises(HTTPException) as exc:
        if change == "owner":
            s.list(rows, owner=UUID(int=10), filters=[None,None,None], page=2, page_size=2, snapshot=first.ranking_snapshot)
        else:
            listing(s, rows, page=2, page_size=2, snapshot=first.ranking_snapshot)
    assert exc.value.status_code == 409


def test_explicit_n_after_global_ranking_and_not_page_size(tmp_path, monkeypatch):
    rows = applicants()
    s = service(tmp_path, rows, {17: .9, 16: .8, 15: .7}, monkeypatch)
    result = listing(s, rows, top_n=5, page_size=2)
    assert result.total == 5 and result.total_pages == 3
    assert [i.cv_id.int for i in result.items] == [17, 16]
    assert listing(s, rows[:3], top_n=5).total == 3
    with pytest.raises(HTTPException) as exc: listing(s, rows, page=2)
    assert exc.value.status_code == 422


def test_all_availability_states_null_fallback_and_outage(tmp_path, monkeypatch):
    rows = applicants(4)
    s = service(tmp_path, rows, {1: "pending", 2: "unavailable", 3: "error", 4: .6}, monkeypatch)
    result = listing(s, rows)
    assert [i.cv_id.int for i in result.items] == [4,1,2,3]
    assert [i.ranking_status for i in result.items] == ["ranked","pending","unavailable","error"]
    assert all(i.ai_rank is None and i.semantic_match_score is None for i in result.items[1:])


class Provider:
    def __init__(self, failure=False): self.calls = []; self.failure = failure
    async def embed_many(self, texts):
        self.calls.append(texts)
        if self.failure: raise RuntimeError("safe simulated outage")
        return EmbeddingBatchResult(vectors=(tuple([1.] + [0.]*1023),), provider="ollama", model="bge-m3", dimensions=1024)


async def verified(): pass


@pytest.mark.parametrize("kind", ["cv", "job"])
def test_precompute_reuses_exact_profile_and_recomputes_changes(tmp_path, monkeypatch, kind):
    cache = RankingCache(tmp_path)
    canonical = cv() if kind == "cv" else __import__("app.services.matching_input_mapper", fromlist=["build_job_matching_input"]).build_job_matching_input(applicants(1)[0].job)
    p = Provider()
    asyncio.run(cache.precompute(kind, canonical, p, verified))
    asyncio.run(cache.precompute(kind, canonical, p, verified))
    assert len(p.calls) == 1 and p.calls[0] == [canonical.semantic_text]
    assert cache.vector(kind, canonical)[0] == "ranked"
    changed = canonical.model_copy(update={"semantic_text": canonical.semantic_text + " Java"})
    assert cache.vector(kind, changed)[0] == "pending"
    asyncio.run(cache.precompute(kind, changed, p, verified))
    assert len(p.calls) == 2
    for field, value in [("embedding_num_batch", 2048), ("ranking_model_digest", "different")]:
        with monkeypatch.context() as m:
            m.setattr(settings, field, value)
            assert cache.vector(kind, canonical)[0] == "pending"
    assert cache.vector(kind, canonical)[0] == "ranked"
    payload = next((tmp_path / "vectors").glob("*.json")).read_text()
    assert canonical.semantic_text not in payload and "Display only" not in payload


def test_provider_error_never_fakes_vector(tmp_path):
    cache = RankingCache(tmp_path); p = Provider(True)
    asyncio.run(cache.precompute("cv", cv(), p, verified))
    assert len(p.calls) == 1
    assert cache.vector("cv", cv()) == ("error", None)


def test_corrupt_cache_and_expired_snapshot_fail_safely(tmp_path):
    cache = RankingCache(tmp_path)
    key = digest(entity_identity("cv", cv()))
    cache.write("vectors", key, {"identity": entity_identity("cv", cv()), "vector": [0.]*1024, "dimensions": 1024})
    assert cache.vector("cv", cv()) == ("error", None)
    token = cache.save_snapshot("bound", [])
    cache.write("snapshots", token, {"binding":"bound", "rows":[], "expires":0})
    assert cache.load_snapshot(token, "bound") is None


def test_source_conflict_valid_canonical_has_no_special_rank_penalty(tmp_path):
    from app.services.cv_source_consistency import validate_source_grounded
    result, _, _, _ = validate_source_grounded("May 2023 to March 2023 Developer ABC Build APIs",
        {"experiences":[{"position":"Developer","company_name":"ABC","description":"Build APIs", "start_date":"May 2023","end_date":"March 2023"}]})
    canonical = build_cv_matching_input(NS(id=UUID(int=1)), result)
    assert canonical.experiences[0].date_consistency.chronology_usable is False
    assert "SOURCE_DATA_CONFLICT" not in canonical.semantic_text
    cache = RankingCache(tmp_path)
    asyncio.run(cache.precompute("cv", canonical, Provider(), verified))
    assert cache.vector("cv", canonical)[0] == "ranked"


def test_batch_selection_matches_confirmed_and_latest_success_policy(monkeypatch):
    cvs = [NS(id=UUID(int=i), source_type=CVSourceType.UPLOADED) for i in (1,2,3)]
    class Query:
        def filter(self,*a): return self
        def order_by(self,*a): return self
        def all(self): return [NS(cv_id=cvs[0].id, status=__import__("app.models.cv_extraction",fromlist=["CVExtractionStatus"]).CVExtractionStatus.SUCCEEDED,
            confirmed_at=True, structured_result={}), NS(cv_id=cvs[1].id,
            status=__import__("app.models.cv_extraction",fromlist=["CVExtractionStatus"]).CVExtractionStatus.SUCCEEDED,
            confirmed_at=None, structured_result={})]
    s = MatchingInputService(NS(query=lambda *a: Query()))
    calls=[]
    monkeypatch.setattr("app.services.matching_input_service.build_cv_matching_input",lambda value, structured=None: calls.append((value.id, structured)) or cv(value.id.int))
    result = s.build_cv_inputs(cvs)
    assert calls[0][1] is None and isinstance(calls[1][1], StructuredCVExtractionResult)
    assert isinstance(result[cvs[2].id], CVNotReadyForMatchingError)


def test_cv_and_job_router_hooks_are_one_entity_after_success(monkeypatch):
    from fastapi import BackgroundTasks
    from app.routers import cvs, recruiters
    entity = NS(id=UUID(int=90))
    class CVServiceFake:
        def __init__(self, db): pass
        def create_cv(self, *args): return entity
        def update_cv(self, *args): return entity
    class JobServiceFake:
        def __init__(self, db): pass
        def create_job(self, *args): return entity
        def update_job(self, *args): return entity
    monkeypatch.setattr(cvs, "CVService", CVServiceFake)
    monkeypatch.setattr(recruiters, "RecruiterJobService", JobServiceFake)
    calls=[]
    async def record(kind, key): calls.append((kind,key))
    monkeypatch.setattr(cvs,"precompute_entity",record)
    monkeypatch.setattr(recruiters,"precompute_entity",record)
    for fn, args in [(cvs.create_my_cv, {"payload":None}),
                     (cvs.update_my_cv, {"payload":None,"cv_id":entity.id}),
                     (recruiters.create_my_job, {"payload":None}),
                     (recruiters.update_my_job, {"payload":None,"job_id":entity.id})]:
        tasks=BackgroundTasks()
        assert fn(**args,background_tasks=tasks,current_user=None,db=None) is entity
        assert len(tasks.tasks)==1
        asyncio.run(tasks())
    assert calls == [("cv",entity.id),("cv",entity.id),("job",entity.id),("job",entity.id)]


def test_lifecycle_task_closes_own_session_before_provider(monkeypatch):
    from app.services import ranking_precompute as module
    events=[]
    class Session:
        def __enter__(self): events.append("open"); return self
        def __exit__(self,*a): events.append("closed")
    class Inputs:
        def __init__(self,db): pass
        def build_cv_input(self,key): return cv(key.int)
    class Cache:
        async def precompute(self,kind,value):
            assert events == ["open","closed"]
            events.append("embedded")
    monkeypatch.setattr(module.database,"SessionLocal",Session)
    monkeypatch.setattr(module,"MatchingInputService",Inputs)
    monkeypatch.setattr(module,"RankingCache",Cache)
    asyncio.run(module.precompute_entity("cv",UUID(int=1)))
    assert events[-1]=="embedded"
