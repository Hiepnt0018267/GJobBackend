"""Synthetic operational stress tests; no real provider, PII, or DEV database."""
import asyncio
import json
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.models.application import JobApplicationStatus
from app.services.ranking_cache import RankingCache, digest, entity_identity
from app.services.semantic_matching_service import cosine_similarity
from test_applicant_ranking import applicants, cv, service, listing, Provider, verified


@pytest.mark.parametrize("bad", [[], "broken", {"unexpected":True}])
def test_corrupt_cache_payload_never_crashes_list(tmp_path,bad):
    cache=RankingCache(tmp_path)
    cache.write("vectors",digest(entity_identity("cv",cv())),bad)
    assert cache.vector("cv",cv())==("error",None)


@pytest.mark.parametrize("vector", [[0.]*1024, [float("nan")]+[0.]*1023,
                                   [float("inf")]+[0.]*1023, [1.,0.], [True]+[0.]*1023])
def test_invalid_vectors_do_not_enter_cosine_or_sort(tmp_path,monkeypatch,vector):
    cache=RankingCache(tmp_path)
    identity=entity_identity("cv",cv())
    monkeypatch.setattr(cache,"read",lambda *a:{"identity":identity,"vector":vector,"dimensions":len(vector)})
    assert cache.vector("cv",cv())==("error",None)
    with pytest.raises(RuntimeError):
        if len(vector)==2: cosine_similarity(vector,[1.]*1024)
        else: cosine_similarity(vector,vector)


def test_duplicate_application_boundary_is_rejected(tmp_path,monkeypatch):
    rows=applicants(3);s=service(tmp_path,rows,{1:.8,2:.7,3:.6},monkeypatch)
    with pytest.raises(HTTPException) as exc:
        listing(s,rows+[rows[0]])
    assert exc.value.status_code==409


@pytest.mark.parametrize("fault", ["duplicate", "unknown_id", "bad_status", "bad_score", "bad_rank", "non_list"])
def test_corrupt_snapshot_fails_closed_not_duplicate_or_skip(tmp_path,monkeypatch,fault):
    rows=applicants(3);s=service(tmp_path,rows,{1:.8,2:.7,3:.6},monkeypatch)
    first=listing(s,rows,page_size=2)
    stored=s.cache.read("snapshots",first.ranking_snapshot)
    if fault=="duplicate":stored["rows"][1]=stored["rows"][0]
    elif fault=="unknown_id":stored["rows"][1]["id"]=str(UUID(int=99999))
    elif fault=="bad_status":stored["rows"][1]["ranking_status"]="imaginary"
    elif fault=="bad_score":stored["rows"][1]["semantic_match_score"]="not a number"
    elif fault=="bad_rank":stored["rows"][1]["ai_rank"]=900
    else:stored["rows"]={}
    s.cache.write("snapshots",first.ranking_snapshot,stored)
    with pytest.raises(HTTPException) as exc:
        listing(s,rows,page=2,page_size=2,snapshot=first.ranking_snapshot)
    assert exc.value.status_code==409


@pytest.mark.parametrize("count",[0,1,100])
@pytest.mark.parametrize("state",["pending", .7])
def test_empty_single_scale_and_all_pending_or_tied(tmp_path,monkeypatch,count,state):
    rows=applicants(count)
    s=service(tmp_path,rows,{i+1:state for i in range(count)},monkeypatch)
    result=listing(s,rows,page_size=100)
    assert result.total==count and len(result.items)==count
    assert [i.id for i in result.items]==[a.id for a in rows]
    assert s.cache.lookups==count+(1 if count else 0)
    assert all(i.semantic_match_score is None for i in result.items) if state=="pending" else all(i.ai_rank==n for n,i in enumerate(result.items,1))


def test_near_ties_full_precision_limit_and_serialization(tmp_path,monkeypatch):
    rows=applicants(4)
    s=service(tmp_path,rows,{1:.699998,2:.699999,3:.700000},monkeypatch)
    result=listing(s,rows,top_n=2)
    assert [r.cv_id.int for r in result.items]==[3,2]
    encoded=json.loads(result.model_dump_json())
    assert [r['semantic_match_score'] for r in encoded['items']]==[.7,.699999]
    s.cache.signals[4]=.700001
    old=listing(s,rows,top_n=2,snapshot=result.ranking_snapshot)
    fresh=listing(s,rows,top_n=2)
    assert [r.cv_id.int for r in old.items]==[3,2]
    assert [r.cv_id.int for r in fresh.items]==[4,3]


def test_same_cv_across_jobs_reuses_vector_not_pair_score(tmp_path,monkeypatch):
    from app.services.applicant_ranking_service import ApplicantRankingService
    rows=applicants(2)
    rows[1].cv=rows[0].cv;rows[1].cv_id=rows[0].cv_id
    rows[1].job=__import__('copy').copy(rows[0].job)
    rows[1].job.id=UUID(int=1001);rows[1].job.description="Different job";rows[1].job_id=rows[1].job.id
    s=service(tmp_path,rows,{},monkeypatch);calls=[]
    def vectors(kind,canonical):
        calls.append((kind,getattr(canonical,'cv_id',getattr(canonical,'job_id',None))))
        return "ranked", [1.,0.] if kind=="cv" or canonical.job_id==UUID(int=1000) else [0.,1.]
    monkeypatch.setattr(s.cache,"vector",vectors)
    result=listing(s,rows)
    assert len(calls)==3 and sum(k=='cv' for k,_ in calls)==1
    assert [r.semantic_match_score for r in result.items]==[1.,0.]


def test_provider_failure_precompute_retry_bounded_and_no_fake_zero(tmp_path):
    cache=RankingCache(tmp_path);p=Provider(True)
    asyncio.run(cache.precompute("cv",cv(),p,verified))
    assert cache.vector("cv",cv())==("error",None) and len(p.calls)==1
    restored=Provider()
    asyncio.run(cache.precompute("cv",cv(),restored,verified))
    assert cache.vector("cv",cv())[0]=="ranked" and len(restored.calls)==1
    asyncio.run(cache.precompute("cv",cv(),restored,verified))
    assert len(restored.calls)==1


def test_explicit_overflow_production_precompute_visible_error(tmp_path,monkeypatch):
    from app.embeddings import EmbeddingInputTooLongError
    class Overflow:
        async def embed_many(self,texts): raise EmbeddingInputTooLongError('Synthetic overflow')
    cache=RankingCache(tmp_path)
    asyncio.run(cache.precompute('cv',cv(),Overflow(),verified))
    assert cache.vector('cv',cv())==('error',None)
    rows=applicants(1);s=service(tmp_path,rows,{},monkeypatch)
    monkeypatch.setattr(s.cache,'vector',lambda kind,value:cache.vector(kind,value) if kind=='cv' else ('ranked',[1.,0.]))
    result=listing(s,rows)
    assert result.total==1 and result.items[0].ranking_status=='error'
    assert result.items[0].semantic_match_score is None and result.items[0].ai_rank is None


def test_arrival_invalidates_old_snapshot_new_snapshot_has_full_set(tmp_path,monkeypatch):
    rows=applicants(5);s=service(tmp_path,rows,{1:.8},monkeypatch)
    first=listing(s,rows,page_size=2)
    rows.append(applicants(6)[-1]);rows.sort(key=lambda a:(a.created_at,a.id),reverse=True)
    with pytest.raises(HTTPException) as exc: listing(s,rows,page=2,page_size=2,snapshot=first.ranking_snapshot)
    assert exc.value.status_code==409
    assert listing(s,rows).total==6


def test_legacy_payload_miss_and_crash_lease_stay_visible_pending(tmp_path,monkeypatch):
    cache=RankingCache(tmp_path);identity=entity_identity('cv',cv())
    old={**identity,'canonical_version':'legacy-v1'}
    cache.write('vectors',digest(identity),{'identity':old,'status':'ranked','vector':[1.]+[0.]*1023,'dimensions':1024})
    assert cache.vector('cv',cv())==('pending',None)
    p=Provider()
    with cache.lease(digest(identity)) as owned:
        assert owned
        asyncio.run(cache.precompute('cv',cv(),p,verified))
        assert p.calls==[]
    rows=applicants(5);s=service(tmp_path,rows,{},monkeypatch)
    first=listing(s,rows,page_size=2)
    second=listing(s,rows,page=2,page_size=2,snapshot=first.ranking_snapshot)
    assert first.total==second.total==5
    assert all(r.ranking_status=='pending' and r.semantic_match_score is None for r in [*first.items,*second.items])
