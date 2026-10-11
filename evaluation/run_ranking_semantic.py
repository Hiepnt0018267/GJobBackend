"""Task14C.2 production-canonical scoring separated from labeled measurement."""
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from dataclasses import asdict
import httpx
from evaluation.common import iter_csv,EvaluationDataError
from evaluation.labeling_store import atomic_csv
from evaluation.ranking_metrics import POLICY,full_rank,summarize,random_sanity

HASHES={'ranking_pairs_labeled.csv':'a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d',
        'ranking_canonical_cvs.jsonl':'0a7da44fde0cde5f0ff45259093bb7f194cbc40bea502bf02c50bfe66682f615',
        'ranking_canonical_jds.jsonl':'9da55f0731adf98c1c7aefe7072759effc04816f6568ddee9caef9f1e14fedc1',
        'ranking_canonical_pair_manifest.csv':'cd715793e5ba37272d7cd1b82847f58e78879b1aaaf2577efab1c520f1ae92b9'}
PAIR_FIELDS=('ranking_case_id','job_id','cv_id','pair_id')
SEMANTIC_CORE_SHA256='0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf'
PRED_FIELDS=[*PAIR_FIELDS,'semantic_score','rank','relevance_grade','is_relevant_primary']
ERROR_FIELDS=['ranking_case_id','job_id','error_type','pair_id','rank','semantic_score','relevance_grade','comparison_pair_id','comparison_rank','comparison_semantic_score','comparison_relevance_grade']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_hashes(directory,expected=HASHES):
    for name,value in expected.items():
        if sha(Path(directory)/name)!=value:raise EvaluationDataError('FROZEN_HASH_MISMATCH:'+name)


def load_inputs(args):
    from evaluation import prepare_ranking_canonical as prep
    from app.schemas.matching import CanonicalCVMatchingInput,CanonicalJobMatchingInput
    verify_hashes(args.input_dir)
    summary=json.loads(Path('evaluation/results/ranking-canonical-inputs/summary.json').read_text(encoding='utf-8'))
    if not summary.get('frozen'):raise EvaluationDataError('CANONICAL_NOT_FROZEN')
    rows=[r for _,r in iter_csv(args.input_dir/'ranking_pairs_labeled.csv')]
    manifest=[r for _,r in iter_csv(args.input_dir/'ranking_canonical_pair_manifest.csv')]
    cvs,jds,source_hashes=prep.sources(args.data_dir);prep.validate(rows,cvs,jds,labeled=True)
    profile=summary['profile'];ce={r['cv_id']:prep.envelope('cv',r['cv_id'],prep.resolve(r['cv_id'],r['candidate_source_ref'],cvs),source_hashes,profile) for r in rows}
    selected={r['job_id'] for r in rows};raw_jobs={r['job_id']:r for _,r in iter_csv(prep.locate_source(args.data_dir,'job_postings.csv')) if r['job_id'] in selected}
    je={r['job_id']:prep.envelope('job',r['job_id'],{**prep.resolve(r['job_id'],r['job_source_ref'],jds),'raw':raw_jobs[r['job_id']]},source_hashes,profile) for r in rows}
    cv_records=prep.read_records(args.input_dir/'ranking_canonical_cvs.jsonl',ce,'cv',source_texts={k:cvs[k]['text'] for k in ce})
    jd_records=prep.read_records(args.input_dir/'ranking_canonical_jds.jsonl',je,'job')
    for k,r in jd_records.items():
        if prep.canonical_jd(k,raw_jobs[k]).model_dump(mode='json')!=r['canonical_input']:raise EvaluationDataError('JD_REPLAY_MISMATCH')
    expected_manifest=prep.pair_manifest(rows,cv_records,jd_records,args.input_dir/'ranking_canonical_cvs.jsonl',args.input_dir/'ranking_canonical_jds.jsonl')
    if manifest!=expected_manifest or any(r['ready_for_scoring']!='true' for r in manifest):raise EvaluationDataError('MANIFEST_NOT_READY')
    from collections import Counter
    if len(rows)!=100 or len(ce)!=95 or len(je)!=10:raise EvaluationDataError('COVERAGE_MISMATCH')
    counts=Counter(r['ranking_case_id'] for r in rows)
    if len(counts)!=10 or set(counts.values())!={10}:raise EvaluationDataError('POOL_COVERAGE_MISMATCH')
    # Labels NEVER go to score layer. Only these manifest identity fields do.
    pairs=[{k:r[k] for k in PAIR_FIELDS} for r in manifest]
    models_cv={k:CanonicalCVMatchingInput.model_validate(r['canonical_input']) for k,r in cv_records.items()}
    models_jd={k:CanonicalJobMatchingInput.model_validate(r['canonical_input']) for k,r in jd_records.items()}
    return pairs,models_cv,models_jd,rows


class CanonicalVectorCache:
    def __init__(self,provider,directory,identity):
        self.provider=provider;self.directory=Path(directory);self.identity=identity
        self.by_text={};self.metadata=None;self.hits=0;self.misses=0

    async def preload(self,entities):
        from evaluation.prepare_ranking_canonical import atomic_json
        from app.services.semantic_matching_service import cosine_similarity
        for kind,key,model,fingerprint in entities:
            text=model.semantic_text;text_hash=hashlib.sha256(text.encode()).hexdigest()
            binding={'identity':self.identity,'canonical_fingerprint':fingerprint,'text_sha256':text_hash}
            cache_key=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest();path=self.directory/(cache_key+'.json')
            if path.exists():
                value=json.loads(path.read_text(encoding='utf-8'))
                if value['binding']!=binding:raise EvaluationDataError('CACHE_BINDING_MISMATCH')
                self.hits+=1
            else:
                result=await self.provider.embed_many([text])
                if len(result.vectors)!=1:raise EvaluationDataError('EMBEDDING_COUNT_MISMATCH')
                value={'binding':binding,'vector':list(result.vectors[0]),'provider':result.provider,'model':result.model,'dimensions':result.dimensions,'prompt_eval_count':getattr(self.provider,'last_prompt_eval_count',None)}
                cosine_similarity(value['vector'],value['vector'])
                atomic_json(path,value);self.misses+=1
            vector=tuple(value['vector']);cosine_similarity(vector,vector)
            if value['provider']!=self.identity['provider'] or value['model'].removesuffix(':latest')!=self.identity['model'].removesuffix(':latest'):
                raise EvaluationDataError('CACHE_MODEL_MISMATCH')
            metadata=(value['provider'],value['model'],value['dimensions'])
            if len(vector)!=metadata[2] or (self.metadata is not None and metadata!=self.metadata):raise EvaluationDataError('VECTOR_METADATA_MISMATCH')
            self.metadata=metadata;self.by_text[text]=vector
            print(f'Canonical embeddings completed {self.hits+self.misses}',flush=True)

    async def embed_many(self,texts):
        from app.embeddings.base import EmbeddingBatchResult
        if self.metadata is None or any(text not in self.by_text for text in texts):raise EvaluationDataError('UNREGISTERED_CANONICAL_TEXT')
        return EmbeddingBatchResult(tuple(self.by_text[t] for t in texts),*self.metadata)


async def score_pairs(pairs,cvs,jds,cache):
    from app.services.semantic_matching_service import SemanticMatchingService
    service=SemanticMatchingService(cache);scores=[]
    for pair in sorted(pairs,key=lambda r:r['pair_id']):
        if set(pair)!=set(PAIR_FIELDS):raise EvaluationDataError('SCORING_IDENTITY_ONLY_NO_LABELS')
        result=await service.match(cvs[pair['cv_id']],jds[pair['job_id']])
        scores.append({**pair,'semantic_score':result.semantic_similarity})
    return scores


async def scoring(args,pairs,cvs,jds):
    from app.core.config import settings
    from app.embeddings.factory import get_embedding_provider
    from app.services.matching_fingerprint import fingerprint_cv,fingerprint_job
    from app.embeddings.profile import profile_fingerprint
    from evaluation.prepare_ranking_canonical import atomic_json
    started=time.perf_counter();verify_hashes(args.input_dir)
    if sha('app/services/semantic_matching_service.py')!=SEMANTIC_CORE_SHA256:raise EvaluationDataError('SEMANTIC_CORE_CHANGED')
    if settings.embedding_provider!='ollama' or settings.embedding_model.removesuffix(':latest')!='bge-m3':raise EvaluationDataError('EXISTING_BGE_CONFIG_REQUIRED')
    # Read-only model identity check, not LLM generation.
    async with httpx.AsyncClient(base_url=settings.ollama_base_url,timeout=settings.embedding_timeout_seconds) as client:
        response=await client.get('/api/tags');response.raise_for_status();tags=response.json()
        response=await client.get('/api/version');response.raise_for_status();provider_version=response.json()['version']
    found=[m for m in tags['models'] if m['name'].removesuffix(':latest')==settings.embedding_model.removesuffix(':latest')]
    if len(found)!=1 or not found[0].get('digest'):raise EvaluationDataError('BGE_MODEL_IDENTITY_MISSING')
    if found[0]['digest']!='7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab':raise EvaluationDataError('FROZEN_BGE_MODEL_CHANGED')
    identity={'provider':settings.embedding_provider,'model':settings.embedding_model,'model_digest':found[0]['digest'],
              'provider_version':provider_version,
              'request_profile':{'endpoint':'/api/embed','truncate':False,'options':{'num_ctx':settings.embedding_num_ctx,'num_batch':settings.embedding_num_batch},'timeout_seconds':settings.embedding_timeout_seconds},
              'shared_profile':get_embedding_provider().profile,
              'shared_profile_fingerprint':profile_fingerprint(get_embedding_provider().profile),
              'canonical_version':'matching-canonical-v3-explicit-identity-contract',
              'semantic_core_sha256':sha('app/services/semantic_matching_service.py'),
              'provider_core_sha256':sha('app/embeddings/ollama_provider.py')}
    protocol={'policy':POLICY,'frozen_hashes':HASHES,'embedding_identity':identity,
              'evaluation_code_sha256':{'metrics':sha('evaluation/ranking_metrics.py'),'runner':sha(__file__)}}
    protocol_path=args.cache_dir/'protocol.json'
    if protocol_path.exists():
        if json.loads(protocol_path.read_text(encoding='utf-8'))!=protocol:raise EvaluationDataError('FROZEN_PROTOCOL_CHANGED')
    else:atomic_json(protocol_path,protocol)
    state_path=args.cache_dir/'scores.json'
    if state_path.exists():
        state=json.loads(state_path.read_text(encoding='utf-8'))
        if state['protocol']!=protocol:raise EvaluationDataError('SCORE_PROTOCOL_MISMATCH')
        return state
    cache=CanonicalVectorCache(get_embedding_provider(),args.cache_dir/'vectors',identity)
    entities=[('cv',k,v,fingerprint_cv(v)) for k,v in sorted(cvs.items())]+[('job',k,v,fingerprint_job(v)) for k,v in sorted(jds.items())]
    # Sanity on the known blocker FIRST, cached once and never embedded twice.
    blocker=[e for e in entities if e[0]=='cv' and e[1]=='16244633']
    if blocker:
        await cache.preload(blocker)
        if cache.metadata[2]!=1024 or getattr(cache.provider,'last_prompt_eval_count',None) not in (None,2076):raise EvaluationDataError('BLOCKER_SANITY_METADATA_MISMATCH')
        print('Blocker CV16244633 PASS under shared context profile',flush=True)
    from evaluation.embedding_admission_gate import actual_admission_gate
    admission=actual_admission_gate(settings.ollama_base_url,settings.embedding_model,entities,cache.provider.profile)
    atomic_json(args.cache_dir/'token_admission.json',admission)
    print(json.dumps({k:admission[k] for k in ('inputs_counted','maximum_total_tokens','count_gt2048','count_gt4096','count_gt8192')},sort_keys=True),flush=True)
    await cache.preload([e for e in entities if e not in blocker])
    scores=await score_pairs(pairs,cvs,jds,cache)
    verify_hashes(args.input_dir)
    state={'protocol':protocol,'scores':scores,'token_admission':admission,'embedding_stats':{'unique_cvs':len(cvs),'unique_jds':len(jds),'unique_texts':len(cache.by_text),'cache_hits':cache.hits,'cache_misses':cache.misses,'provider':cache.metadata[0],'model':cache.metadata[1],'dimensions':cache.metadata[2],'runtime_seconds':time.perf_counter()-started}}
    atomic_json(state_path,state)
    return state


def evaluate(args,state,labels):
    from evaluation.prepare_ranking_canonical import atomic_json
    verify_hashes(args.input_dir)
    if state['protocol']['frozen_hashes']!=HASHES or state['protocol']['policy']!=POLICY:raise EvaluationDataError('PROTOCOL_MISMATCH')
    if state['protocol']['evaluation_code_sha256']!={'metrics':sha('evaluation/ranking_metrics.py'),'runner':sha(__file__)}:raise EvaluationDataError('METRIC_CODE_CHANGED')
    score_rows=full_rank(state['scores']) # ranks frozen BEFORE label join
    indexed={r['pair_id']:r for r in labels}
    if len(score_rows)!=100 or {r['pair_id'] for r in score_rows}!=set(indexed):raise EvaluationDataError('SCORE_COVERAGE_MISMATCH')
    predictions=[]
    for row in score_rows:
        label=indexed[row['pair_id']]
        if any(row[k]!=label[k] for k in PAIR_FIELDS):raise EvaluationDataError('LABEL_IDENTITY_MISMATCH')
        grade=int(label['relevance_grade']);predictions.append({**row,'relevance_grade':grade,'is_relevant_primary':grade>=1})
    metrics,errors,uncertainty=summarize(predictions);random_reference=random_sanity(predictions)
    metrics.update(task='14C.2',algorithm='semantic-v1',frozen_inputs={name:{'path':str(args.input_dir/name),'sha256':value} for name,value in HASHES.items()},policy=POLICY,embedding_stats=state['embedding_stats'],embedding_identity=state['protocol']['embedding_identity'],ground_truth_grade_counts={str(g):sum(r['relevance_grade']==g for r in predictions) for g in (0,1,2)},pairs=100,jobs=10,full_list_ranking=True,production_default_limit=None,explicit_limit_policy='rank all then take first N')
    for name in ('metrics.json','predictions.csv','ranking_errors.csv','bootstrap.json','random_baseline.json'):
        if (args.output/name).exists():raise EvaluationDataError('OUTPUT_EXISTS_NO_SILENT_RERUN')
    atomic_csv(args.output/'predictions.csv',predictions,PRED_FIELDS);atomic_csv(args.output/'ranking_errors.csv',errors,ERROR_FIELDS)
    atomic_json(args.output/'metrics.json',metrics);atomic_json(args.output/'bootstrap.json',uncertainty);atomic_json(args.output/'random_baseline.json',random_reference)
    # Stored-score replay: neither embedding requests nor label-sensitive sort.
    replay=full_rank(state['scores']);assert [(r['pair_id'],r['rank']) for r in replay]==[(r['pair_id'],r['rank']) for r in predictions]
    verify_hashes(args.input_dir)
    print(json.dumps({'pairs':100,'jobs':10,'overall':metrics['overall'],'error_counts':metrics['error_counts'],'cache':state['embedding_stats']},sort_keys=True))


async def run(args):
    pairs,cvs,jds,labels=load_inputs(args)
    if args.phase=='evaluate':
        state=json.loads((args.cache_dir/'scores.json').read_text(encoding='utf-8'))
    else:state=await scoring(args,pairs,cvs,jds)
    if args.phase in ('all','evaluate'):evaluate(args,state,labels)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['all','score','evaluate'],default='all')
    parser.add_argument('--data-dir',type=Path,default=Path('C:/DATN/Datasets'))
    parser.add_argument('--input-dir',type=Path,default=Path('evaluation/data/derived'))
    parser.add_argument('--cache-dir',type=Path,default=Path('evaluation/cache/ranking-semantic-v1-ctx8192-batch4096-v2'))
    parser.add_argument('--output',type=Path,default=Path('evaluation/results/ranking-semantic-v1'))
    asyncio.run(run(parser.parse_args()))


if __name__=='__main__':main()
