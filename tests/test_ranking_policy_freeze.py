"""Contract-level freeze guards. Synthetic only; no embedding/extraction/DB work."""
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.core.config import settings, Settings
from app.embeddings.factory import get_embedding_provider
from app.embeddings.profile import profile_fingerprint
from app.schemas.recruiter_application import ApplicantRankingStatus
from app.services.recruiter_application_service import RecruiterApplicationService
from app.services.semantic_matching_service import SEMANTIC_MATCHING_VERSION
from app.services.matching_text_privacy import MATCHING_CANONICAL_VERSION
from test_applicant_ranking import applicants, service, listing


POLICY_PATH=Path(__file__).resolve().parents[1]/'evaluation/results/ranking-policy-freeze/policy.json'


def policy(): return json.loads(POLICY_PATH.read_text(encoding='utf-8'))


def test_final_policy_scope_and_forbidden_actions():
    p=policy()
    assert p['policy_version']=='recruiter-ranking-policy-v1' and p['frozen']
    assert p['algorithm']==SEMANTIC_MATCHING_VERSION and p['activation']=='opt-in'
    assert p['threshold'] is None and p['missing_signal_score'] is None
    assert p['full_logical_result_set_default'] and p['human_review_required']
    for key in ('auto_hide','auto_reject','auto_shortlist','auto_hire','auto_status_mutation','auto_decision_notification'):
        assert p[key] is False
    assert p['fairness_claim']=='not_established' and p['protected_group_disparity']=='not_measured'
    assert p['task_14c_complete'] and not p['deployment_performed']
    assert not any('threshold' in name and ('semantic' in name or 'ranking' in name) for name in Settings.model_fields)


def test_actual_factory_profile_matches_frozen_contract_without_network():
    p=policy();profile=get_embedding_provider().profile
    for key in ('provider','model','version','num_ctx','num_batch','truncate','vector_postprocessing'):
        assert profile[key]==p['embedding_profile'][key]
    assert profile_fingerprint(profile)==p['embedding_profile']['profile_fingerprint']
    assert settings.ranking_model_digest==p['embedding_profile']['model_digest']
    assert MATCHING_CANONICAL_VERSION==p['canonical_version']
    assert set(s.value for s in ApplicantRankingStatus)==set(p['ranking_states'])


def test_default_service_path_needs_no_ai_and_keeps_repository_order(monkeypatch):
    rows=applicants(4);calls=[]
    class Repository:
        def list_owned_applications(self,*args): calls.append(args);return rows,len(rows)
    # Inject the repository without filesystem/DB construction. Exercise PUBLIC
    # service method with its actual default argument, not a separate sorter.
    s=RecruiterApplicationService.__new__(RecruiterApplicationService)
    s.repository=Repository();s.db=None
    def forbidden(*args,**kwargs): raise AssertionError('Default path invoked AI')
    monkeypatch.setattr('app.services.applicant_ranking_service.ApplicantRankingService',forbidden)
    result=s.list_applications(SimpleNamespace(id=UUID(int=900)),None,None,None,1,20)
    assert [i.id for i in result.items]==[a.id for a in rows]
    assert all(i.ai_rank is None and i.semantic_match_score is None for i in result.items)
    assert result.ranking_snapshot is None and len(calls)==1
    actual=inspect.signature(RecruiterApplicationService.list_applications).parameters['sort'].default
    assert actual.value==policy()['default_sort']


def test_frozen_no_threshold_null_states_and_business_status_invariance(tmp_path,monkeypatch):
    rows=applicants(6);before=[a.status for a in rows]
    s=service(tmp_path,rows,{1:.95,2:.40,3:.01,4:'pending',5:'unavailable',6:'error'},monkeypatch)
    result=listing(s,rows)
    assert result.total==6 and [i.cv_id.int for i in result.items]==[1,2,3,4,5,6]
    assert [i.semantic_match_score for i in result.items[:3]]==[.95,.40,.01]
    assert all(i.semantic_match_score is None and i.ai_rank is None for i in result.items[3:])
    assert [a.status for a in rows]==before
    assert [i.ranking_status.value for i in result.items[3:]]==['pending','unavailable','error']


def test_frozen_snapshot_and_explicit_n_contract(tmp_path,monkeypatch):
    rows=applicants(17);s=service(tmp_path,rows,{17:.9,16:.8},monkeypatch)
    first=listing(s,rows,page_size=5)
    assert first.total==17 and first.items[0].cv_id.int==17
    s.cache.signals[10]=.99
    ids=[i.id for i in first.items]
    for page in (2,3,4):
        ids.extend(i.id for i in listing(s,rows,page=page,page_size=5,snapshot=first.ranking_snapshot).items)
    assert len(ids)==len(set(ids))==17
    fresh=listing(s,rows,top_n=5)
    assert fresh.total==5 and fresh.items[0].cv_id.int==10
    assert listing(s,rows[:3],top_n=5).total==3


def test_extreme_integer_cache_corruption_is_safe(tmp_path,monkeypatch):
    from app.services.ranking_cache import RankingCache,entity_identity
    from test_applicant_ranking import cv
    cache=RankingCache(tmp_path)
    monkeypatch.setattr(cache,'read',lambda *a:{'identity':entity_identity('cv',cv()),
        'status':'ranked','vector':[10**400]+[0.]*1023,'dimensions':1024})
    assert cache.vector('cv',cv())==('error',None)


def test_extreme_integer_snapshot_corruption_is_safe():
    from app.services.applicant_ranking_service import ApplicantRankingService
    rows=applicants(1)
    stored=[{'id':str(rows[0].id),'ranking_status':'ranked','ai_rank':1,'semantic_match_score':10**400}]
    assert not ApplicantRankingService._valid_snapshot_rows(stored,rows,None)
