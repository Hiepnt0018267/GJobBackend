import asyncio
import copy
import math
from types import SimpleNamespace
import pytest
from app.embeddings.base import EmbeddingBatchResult
from evaluation.ranking_metrics import dcg,pool_metrics,full_rank,summarize,bootstrap
from evaluation.run_ranking_semantic import verify_hashes,score_pairs,CanonicalVectorCache
from evaluation.common import EvaluationDataError


def rows(case='case',grades=None,scores=None):
    grades=grades or [2,1]+[0]*8;scores=scores or [1-i/20 for i in range(10)]
    return [{'ranking_case_id':case,'job_id':case,'cv_id':f'cv{i}','pair_id':f'{case}_p{i:02}','semantic_score':scores[i],'relevance_grade':grades[i]} for i in range(10)]


def test_manual_metrics_and_ndcg_order():
    result=pool_metrics([2,1]+[0]*8)
    assert result['precision@3']==2/3 and result['recall@1']==.5 and result['reciprocal_rank']==1
    assert dcg([2,1,0],3)==3+1/math.log2(3)
    assert pool_metrics([2,1,0],ks=(1,3),ndcg_ks=(3,))['ndcg@3']>pool_metrics([1,2,0],ks=(1,3),ndcg_ks=(3,))['ndcg@3']>pool_metrics([0,1,2],ks=(1,3),ndcg_ks=(3,))['ndcg@3']


def test_full_pool_tie_sort_label_independent():
    data=rows(scores=[.5]*10);ranked=full_rank(list(reversed(data)))
    assert len(ranked)==10 and [r['rank'] for r in ranked]==list(range(1,11))
    other=copy.deepcopy(data)
    for r in other:r['relevance_grade']=0
    assert [r['pair_id'] for r in full_rank(other)]==[r['pair_id'] for r in ranked]
    assert pool_metrics([r['relevance_grade'] for r in ranked])['precision@3']==2/3


def test_primary_grades_macro_not_micro_and_job_bootstrap():
    a=full_rank(rows('a',[1]+[0]*9));b=full_rank(rows('b',[1]*9+[0]))
    result,errors,ci=summarize(a+b)
    assert result['overall']['recall@1']==(1+1/9)/2
    assert result['overall']['precision@1']==1
    assert ci['unit']=='job' and ci['resamples']==1000
    assert ci==bootstrap(result['per_job'])
    assert result['strict_grade2']['undefined_queries']==2 and result['strict_grade2']['reciprocal_rank'] is None


def test_mrr_full_list_and_empty_relevance_undefined():
    result=pool_metrics([0]*9+[1]);assert result['reciprocal_rank']==.1 and result['recall@5']==0
    result=pool_metrics([0]*10);assert result['reciprocal_rank'] is None and result['recall@3'] is None
    with pytest.raises(ValueError):pool_metrics([1],ks=(3,),ndcg_ks=())


def test_invalid_coverage_duplicate_nan_rejected():
    with pytest.raises(ValueError):full_rank(rows()+rows())
    data=rows();data[0]['semantic_score']=float('nan')
    with pytest.raises(ValueError):full_rank(data)
    with pytest.raises(ValueError):summarize(full_rank(rows()[:3]))


def test_hash_mismatch_stops(tmp_path):
    (tmp_path/'input.csv').write_text('changed')
    with pytest.raises(EvaluationDataError,match='HASH_MISMATCH'):verify_hashes(tmp_path,{'input.csv':'0'*64})


def test_score_layer_identity_only_and_production_service(monkeypatch):
    import app.services.semantic_matching_service as production
    calls=[]
    class FakeService:
        def __init__(self,provider):pass
        async def match(self,cv,jd):calls.append((cv,jd));return SimpleNamespace(semantic_similarity=.7)
    monkeypatch.setattr(production,'SemanticMatchingService',FakeService)
    pair={k:v for k,v in rows()[0].items() if k in ('ranking_case_id','job_id','cv_id','pair_id')}
    output=asyncio.run(score_pairs([pair],{pair['cv_id']:'CANONICAL_CV'},{pair['job_id']:'CANONICAL_JD'},None))
    assert calls==[('CANONICAL_CV','CANONICAL_JD')] and 'relevance_grade' not in output[0]
    with pytest.raises(EvaluationDataError):asyncio.run(score_pairs([dict(pair,relevance_grade=2)],{}, {},None))


def test_cache_private_identity_text_fingerprint_and_zero_repeat_calls(tmp_path):
    class FakeProvider:
        calls=0
        async def embed_many(self,texts):self.calls+=1;return EmbeddingBatchResult(((1.,0.),),'ollama','bge-m3',2)
    provider=FakeProvider();identity={'provider':'ollama','model':'bge-m3','model_digest':'frozen','request_profile':{}}
    entities=[('cv','id',SimpleNamespace(semantic_text='private synthetic text'),'fp1')]
    a=CanonicalVectorCache(provider,tmp_path,identity);asyncio.run(a.preload(entities));assert provider.calls==1
    b=CanonicalVectorCache(provider,tmp_path,identity);asyncio.run(b.preload(entities));assert b.hits==1 and provider.calls==1
    assert all('private synthetic text' not in p.read_text() for p in tmp_path.glob('*.json'))
    entities[0]=('cv','id',SimpleNamespace(semantic_text='private synthetic text'),'fp2')
    asyncio.run(b.preload(entities));assert provider.calls==2
