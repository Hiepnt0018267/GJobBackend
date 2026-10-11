"""Frozen synthetic Semantic-v1 stress experiment. No benchmark/DB/LLM access.

Freeze recipe/protocol before requests. Exact-token lengths are chosen solely by
the native tokenizer, before any affected vector is computed. Successful vectors
stay in a separate private text-hash cache. Never retry a failed request.
"""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time
from types import SimpleNamespace
from uuid import UUID

from app.core.config import settings
from app.embeddings.factory import get_embedding_provider
from app.embeddings import EmbeddingInputTooLongError
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.models.job import JobStatus
from app.services.matching_input_mapper import build_cv_matching_input, build_job_matching_input
from app.services.ranking_cache import RankingCache, runtime_identity, verify_current_model, digest
from app.services.semantic_matching_service import cosine_similarity
from evaluation.embedding_admission_gate import actual_admission_gate


UNIT = "Reviewed service implementations, documented API contracts, tested database transactions, analyzed logs, improved monitoring and maintained reliable software releases. "
PROTOCOL = {
    "task":"14C.5", "recipe_version":"synthetic-robustness-v1", "seed":42,
    "reference_pool":["REFERENCE_CV","TRANSFER_CONTROL","UNRELATED_CONTROL"],
    "material_score_abs_delta":0.05,"material_rank_abs_delta":2,
    "near_tie_gap":0.00001,
    "thresholds_are_arbitrary_diagnostics_not_production_policy":True,
    "keyword_repetitions":[1,5,20],"proxy_repetitions":20,
    "long_target_max_total_tokens":3950,"overflow_target_min_total_tokens":4250,
    "max_embedding_requests":22,"retry_count":0,"sequential":True,
    "model":"bge-m3","num_ctx":8192,"num_batch":4096,"truncate":False,
    "rank_rule":"raw cosine DESC; fixed default application order reference,transfer,unrelated for ties (created_at DESC,id DESC); replace only reference slot",
    "frozen_benchmark_used":False, "no_Qwen_Gemini":True,
    "stop":"Any unexpected request error, profile/digest mismatch, changed recipe/protocol, budget overflow or unavailable same-model tokenizer; one expected synthetic overflow rejection allowed",
}


def reference():
    return {"personal_info":{},"career_objective":"Backend software engineer builds reliable services.",
        "skills":[{"name":s} for s in ["Python","FastAPI","PostgreSQL","Docker"]],
        "experiences":[{"company_name":"Synthetic Company","position":"Backend Engineer",
        "description":"Developed Python and FastAPI REST APIs, designed PostgreSQL schemas, added automated tests, deployed Docker services and monitored reliability."}]}


def cv_model(payload, index=1):
    return build_cv_matching_input(SimpleNamespace(id=UUID(int=index)),StructuredCVExtractionResult.model_validate(payload))


def job_model(description=None,title="Backend Engineer",requirements=None):
    job=SimpleNamespace(id=UUID(int=500),title=title,
        description=description or "Develop reliable backend services using Python, FastAPI and PostgreSQL. Build tested REST APIs and deploy Docker services.",
        requirements=requirements if requirements is not None else "Python, API design, PostgreSQL schemas, automated testing and Docker deployments.",
        skills=[],location=None,industry=None,employment_type=None,experience_level=None,
        level=None,experience_requirement=None,work_mode=None,status=JobStatus.APPROVED,
        salary_type=None,salary_min=None,salary_max=None,salary_fixed=None,salary_currency="USD",vacancies=1)
    return build_job_matching_input(job)


def fixtures():
    base=reference();cvs={"REFERENCE_CV":cv_model(base)}
    transfer=deepcopy(base);transfer['skills']=[{'name':'JavaScript'}]
    transfer['experiences'][0]['position']='Frontend Engineer'
    transfer['experiences'][0]['description']='Built JavaScript interfaces, REST API clients and browser tests.'
    transfer['career_objective']='Frontend engineer builds web interfaces.'
    cvs['TRANSFER_CONTROL']=cv_model(transfer,2)
    unrelated={'career_objective':'Maintain gardens and plants.','skills':[{'name':'Gardening'}],
        'experiences':[{'company_name':'Synthetic Nursery','position':'Gardener','description':'Plant trees, maintain soil and cultivate gardens.'}]}
    cvs['UNRELATED_CONTROL']=cv_model(unrelated,3)
    cvs['VERY_SHORT_CV']=cv_model({'skills':[{'name':'Python'}]})
    cvs['SPARSE_CV']=cv_model({'skills':[{'name':'Python'}],'experiences':[{'company_name':'Synthetic Company','position':'Engineer','description':'Build APIs.'}]})
    for n in (1,5,20):
        value=deepcopy(base);value['career_objective']+=' '+('Python FastAPI PostgreSQL Docker '*n)
        cvs[f'KEYWORD_STUFFED_{n}X']=cv_model(value)
    duplicate=deepcopy(base);duplicate['experiences']*=2
    cvs['DUPLICATED_SECTION_CV']=cv_model(duplicate)
    for key,phrase in {
        'LOCATION_HEAVY_CV':'London Paris Singapore ',
        'SCHOOL_PRESTIGE_HEAVY_CV':'Harvard University Stanford University ',
        'EMPLOYER_PRESTIGE_HEAVY_CV':'Google Microsoft ',
        'LANGUAGE_HEAVY_CV':'English Spanish French German ',
        'NOISY_CV':'PROFILE ### Communication teamwork highly motivated flexible dynamic proactive resume heading '
    }.items():
        value=deepcopy(base);value['career_objective']+=' '+phrase*20
        cvs[key]=cv_model(value)
    identity=deepcopy(base);identity['personal_info']={'full_name':'Synthetic Different Name','email':'synthetic@example.com',
        'phone':'0912345678','address':'Synthetic private street','avatar_url':'https://example.com/synthetic.png'}
    cvs['IDENTITY_VARIANT']=cv_model(identity,99)
    jobs={'REFERENCE_JD':job_model(),
          'VERY_SHORT_JD':job_model('Build Python APIs.','Python Developer','Python'),
          'GENERIC_JD':job_model('Looking for a motivated candidate with communication, teamwork and problem solving skills.','Team Member','Communication and teamwork'),
          'NOISY_JD':job_model(job_model().description+' '+('Our innovative company values excellence, collaboration, motivation and customer service. '*20))}
    return cvs,jobs


def long_cv(n):
    value=reference()
    value['experiences']=[{'company_name':'Synthetic Company','position':'Software Engineer',
        'description':UNIT*min(20,n-i)} for i in range(0,n,20)]
    return cv_model(value)


def freeze(path,payload):
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != payload:raise RuntimeError('FROZEN_PROTOCOL_CHANGED')
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as stream:json.dump(payload,stream,sort_keys=True,indent=2)


def flags(delta,rank_delta,key):
    result=[]
    if abs(delta)>=PROTOCOL['material_score_abs_delta']:result.append('MATERIAL_SCORE_SHIFT')
    if abs(rank_delta)>=PROTOCOL['material_rank_abs_delta']:result.append('MATERIAL_RANK_SHIFT')
    if result:
        for token,name in [('KEYWORD','KEYWORD_STUFFING_SENSITIVITY'),('DUPLICATED','DUPLICATION_SENSITIVITY'),
                           ('HEAVY','PROXY_TEXT_SENSITIVITY'),('NOISY','NOISE_SENSITIVITY')]:
            if token in key:result.append(name)
    return result


def compare_vectors(cvs,jobs):
    pool=['REFERENCE_CV','TRANSFER_CONTROL','UNRELATED_CONTROL']
    base_scores=[cosine_similarity(cvs[key],jobs['REFERENCE_JD']) for key in pool]
    def ranks(scores):return [sorted(range(3),key=lambda i:(-scores[i],i)).index(i)+1 for i in range(3)]
    base_rank=ranks(base_scores);rows=[]
    for key,vector in cvs.items():
        if key in ('TRANSFER_CONTROL','UNRELATED_CONTROL'):continue
        score=cosine_similarity(vector,jobs['REFERENCE_JD'])
        order=ranks([score,*base_scores[1:]])
        delta=score-base_scores[0];movement=order[0]-base_rank[0]
        rows.append({'case_id':key,'kind':'cv','reference_score':base_scores[0],'semantic_score':score,
            'score_delta':delta,'absolute_delta':abs(delta),'reference_rank':base_rank[0],'rank':order[0],
            'rank_delta':movement,'ranking_status':'ranked','flags':flags(delta,movement,key)})
    jd_rows=[]
    for key,vector in jobs.items():
        scores=[cosine_similarity(cvs[name],vector) for name in pool];order=ranks(scores)
        jd_rows.append({'case_id':key,'kind':'jd','scores':scores,'ranks':order,
            'score_deltas':[s-b for s,b in zip(scores,base_scores)],
            'rank_deltas':[r-b for r,b in zip(order,base_rank)],
            'spread':max(scores)-min(scores),'exact_tied_pairs':sum(scores[i]==scores[j] for i in range(3) for j in range(i)),
            'near_tied_pairs':sum(0<abs(scores[i]-scores[j])<=PROTOCOL['near_tie_gap'] for i in range(3) for j in range(i)),
            'flags':sorted(set(flag for i in range(3) for flag in flags(scores[i]-base_scores[i],order[i]-base_rank[i],key)))})
    return rows,jd_rows


async def run(cache_root):
    cvs,jobs=fixtures();cache=RankingCache(cache_root);provider=get_embedding_provider()
    protocol={**PROTOCOL,'identity':runtime_identity(),
        'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'text_hashes':{k:hashlib.sha256(v.semantic_text.encode()).hexdigest() for k,v in {**cvs,**jobs}.items()}}
    freeze(cache_root/'protocol.json',protocol)
    # Refuse rerun of a started/failed experiment. No result-based retry.
    marker=cache_root/'started.json'
    if marker.exists():raise RuntimeError('EXPERIMENT_ALREADY_STARTED_NO_RETRY')
    await verify_current_model()
    freeze(marker,{'protocol_sha256':digest(protocol),'started_at':time.time()})
    calls=0;hits=0;misses=0;vectors={};inventory=[];started=time.perf_counter()
    async def embed(key,canonical,kind,overflow=False):
        nonlocal calls,hits,misses
        identity={'runtime':runtime_identity(),'text_sha256':hashlib.sha256(canonical.semantic_text.encode()).hexdigest()}
        cached=cache.read('experiment-vectors',digest(identity))
        if cached:
            hits+=1;cosine_similarity(cached['vector'],cached['vector']);return cached['vector']
        if calls>=PROTOCOL['max_embedding_requests']:raise RuntimeError('REQUEST_BUDGET_EXHAUSTED')
        calls+=1;misses+=1
        cache.write('experiment-progress','0',{'request_count':calls,'cache_hits':hits,'cache_misses':misses,
            'current_case':key,'phase':'request_started_no_retry'})
        try:
            response=await provider.embed_many([canonical.semantic_text])
        except EmbeddingInputTooLongError:
            if not overflow:raise
            inventory.append({'case_id':key,'kind':kind,'ranking_status':'error','explicit_overlimit_rejection':True})
            return None
        if overflow:raise RuntimeError('OVERLIMIT_UNEXPECTEDLY_ACCEPTED')
        if len(response.vectors)!=1 or response.dimensions!=1024:raise RuntimeError('INVALID_BGE_RESPONSE')
        vector=response.vectors[0];cosine_similarity(vector,vector)
        cache.write('experiment-vectors',digest(identity),{'vector':vector,'identity':identity})
        return vector
    # Short reference request loads the SAME frozen production profile; no server mutation.
    vectors['REFERENCE_CV']=await embed('REFERENCE_CV',cvs['REFERENCE_CV'],'cv')
    # Binary search is TOKENIZER-ONLY and predetermined; no outcomes influence text.
    def choose(builder,target):
        lo,hi=1,350
        while lo<hi:
            mid=(lo+hi+1)//2
            n=count(builder(mid))
            if n<=target:lo=mid
            else:hi=mid-1
        return builder(lo)
    # Native counter discovery/count without an admission exception is supplied
    # below; no separate tokenizer implementation or character approximation.
    from evaluation.token_admission_diagnostics import runtime_token_count
    import subprocess,re,httpx
    show=httpx.post(settings.ollama_base_url.rstrip('/')+'/api/show',json={'model':settings.embedding_model},timeout=20).json()
    model_path=re.search(r'^FROM\s+(.+)$',show['modelfile'],re.M).group(1).strip()
    raw=subprocess.check_output(['powershell','-NoProfile','-Command',"$v=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'llama-server.exe'} | ForEach-Object {if($_.CommandLine -match '--port[ =]+(\\d+)'){$matches[1]}});ConvertTo-Json -InputObject $v -Compress"],text=True)
    selected=[]
    for port in json.loads(raw):
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=20) as client:
            if client.get('/props').json().get('model_path')==model_path:selected.append(port)
    if len(selected)!=1:raise RuntimeError('TOKENIZER_NOT_UNIQUELY_VERIFIED')
    # Gate once to verify physical flags/model before any long input.
    gate=actual_admission_gate(settings.ollama_base_url,settings.embedding_model,
         [('cv','REFERENCE_CV',cvs['REFERENCE_CV'],{})],provider.profile)
    client=httpx.Client(base_url=f'http://127.0.0.1:{selected[0]}',timeout=30)
    def count(model):return runtime_token_count(client,model.semantic_text,add_special=True)['count']
    cvs['VERY_LONG_CV']=choose(long_cv,3950)
    jobs['VERY_LONG_JD']=choose(lambda n:job_model(UNIT*n),3950)
    # Exact smallest repeat count reaching4250; deliberately one rejected embed.
    lo,hi=1,350
    while lo<hi:
        mid=(lo+hi)//2
        if count(long_cv(mid))>=4250:hi=mid
        else:lo=mid+1
    cvs['OVERLIMIT_CV']=long_cv(lo)
    for kind,models in [('cv',cvs),('jd',jobs)]:
        for key,canonical in models.items():
            total=count(canonical)
            if key!='OVERLIMIT_CV' and total>4096:raise RuntimeError('NON_OVERFLOW_CASE_EXCEEDS_CAP')
            if key=='OVERLIMIT_CV' and not 4096<total<=8192:raise RuntimeError('INVALID_OVERFLOW_FIXTURE')
            inventory.append({'case_id':key,'kind':kind,'total_tokens_with_specials':total,
                'characters':len(canonical.semantic_text),'text_sha256':hashlib.sha256(canonical.semantic_text.encode()).hexdigest()})
    freeze(cache_root/'case_inventory.json',inventory)
    # All exact case identities/counts frozen before their remaining requests.
    try:
        for kind,models in [('cv',cvs),('jd',jobs)]:
            for key,canonical in models.items():
                if key=='REFERENCE_CV':continue
                vectors[key]=await embed(key,canonical,kind,key=='OVERLIMIT_CV')
    finally:client.close()
    await verify_current_model()
    cv_vectors={k:vectors[k] for k in cvs if vectors[k] is not None}
    jd_vectors={k:vectors[k] for k in jobs}
    cv_rows,jd_rows=compare_vectors(cv_vectors,jd_vectors)
    metrics={'task':'14C.5','protocol':protocol,'runtime_gate':gate,
        'case_inventory':inventory,'cv_perturbations':cv_rows,'jd_perturbations':jd_rows,
        'live_embedding_requests':calls,'cache_hits':hits,'cache_misses':misses,
        'runtime_seconds':time.perf_counter()-started,'Qwen_Gemini_calls':0,'DB_access':False,
        'keyword_scores':[next(r['semantic_score'] for r in cv_rows if r['case_id']==f'KEYWORD_STUFFED_{n}X') for n in (1,5,20)]}
    freeze(cache_root/'completed.json',metrics)
    return metrics


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache-root',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(asyncio.run(run(args.cache_root)),indent=2))


if __name__=='__main__':main()
