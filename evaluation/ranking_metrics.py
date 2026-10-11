"""Frozen offline query-level ranking measurement, no scoring/model imports."""
import math
import random
import statistics
from collections import Counter,defaultdict
from evaluation.benchmark_metrics import distribution

POLICY={'primary_relevant':'grade >= 1','precision_recall_k':[1,3,5],
        'ndcg_k':[1,3,5,10],'gain':'2^grade - 1','discount':'log2(rank + 1)',
        'tie_policy':'semantic_score DESC, pair_id ASC','aggregation':'macro by job',
        'full_list_ranking':True,'production_default_limit':None,
        'explicit_limit_policy':'rank all then take first N','bootstrap_resamples':1000,'seed':42,
        'strict_grade2_zero_positive':'undefined, excluded from secondary averages; query retained',
        'deep_list_inversion':'grade 0 at least 3 ranks above at least 2 grade1 candidates'}


def dcg(grades,k):
    return math.fsum((2**grade-1)/math.log2(rank+1) for rank,grade in enumerate(grades[:k],1))


def pool_metrics(grades,ks=(1,3,5),ndcg_ks=(1,3,5,10),strict=False):
    if any(g not in (0,1,2) for g in grades) or not grades:raise ValueError('Invalid grades')
    if max((*ks,*ndcg_ks),default=0)>len(grades):raise ValueError('K exceeds full pool')
    relevant=[int(g==2 if strict else g>=1) for g in grades];total=sum(relevant)
    first=next((i for i,g in enumerate(relevant,1) if g),None)
    result={'first_relevant_rank':first,'reciprocal_rank':1/first if first else None}
    for k in ks:
        found=sum(relevant[:k]);result[f'precision@{k}']=found/k if total or not strict else None
        result[f'recall@{k}']=found/total if total else None
    if not strict:
        ideal=sorted(grades,reverse=True)
        for k in ndcg_ks:
            denom=dcg(ideal,k);result[f'ndcg@{k}']=dcg(grades,k)/denom if denom else None
    return result


def full_rank(rows):
    by_case=defaultdict(list);seen=set()
    for row in rows:
        if row['pair_id'] in seen:raise ValueError('Duplicate pair')
        seen.add(row['pair_id']);score=float(row['semantic_score'])
        if not math.isfinite(score) or not -1<=score<=1:raise ValueError('Invalid score')
        by_case[row['ranking_case_id']].append(dict(row,semantic_score=score))
    result=[]
    for case,pool in sorted(by_case.items()):
        if len({r['job_id'] for r in pool})!=1 or len({r['cv_id'] for r in pool})!=len(pool):raise ValueError('Pool identity mismatch')
        for rank,row in enumerate(sorted(pool,key=lambda r:(-r['semantic_score'],r['pair_id'])),1):result.append(dict(row,rank=rank))
    return result


def summarize(predictions):
    groups=defaultdict(list)
    for r in predictions:groups[r['ranking_case_id']].append(r)
    per_job=[];errors=[];tie_groups=[];composition={k:Counter() for k in (1,3,5)}
    for case,rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda r:r['rank'])
        if len(rows)!=10 or [r['rank'] for r in rows]!=list(range(1,11)):raise ValueError('Incomplete full ranking')
        grades=[int(r['relevance_grade']) for r in rows];counts=Counter(grades)
        scores=Counter(r['semantic_score'] for r in rows)
        tie_groups.extend({'case':case,'size':n} for n in scores.values() if n>1)
        metrics=pool_metrics(grades);strict=pool_metrics(grades,ndcg_ks=(),strict=True)
        inv=sum(a<b for i,a in enumerate(grades) for b in grades[i+1:])
        per_job.append({'ranking_case_id':case,'job_id':rows[0]['job_id'],'candidate_count':10,
                        'relevant_count':sum(g>=1 for g in grades),'grade2_count':counts[2],
                        'grade_counts':dict(counts),'inversions':inv,**metrics,'strict_grade2':strict})
        for k in composition:composition[k].update(grades[:k])
        def error(kind,row,other=None):
            errors.append({'ranking_case_id':case,'job_id':row['job_id'],'error_type':kind,
                           **{k:row[k] for k in ('pair_id','rank','semantic_score','relevance_grade')},
                           **{f'comparison_{k}':other[k] if other else '' for k in ('pair_id','rank','semantic_score','relevance_grade')}})
        for row in rows:
            grade=int(row['relevance_grade']);rank=row['rank']
            if rank==1 and grade==0:error('TOP1_IRRELEVANT',row)
            if grade==2:
                if rank>3:error('GRADE2_BELOW_TOP3',row)
                if rank>5:error('GRADE2_BELOW_TOP5',row)
            if grade==0:
                below=[r for r in rows if r['rank']>rank]
                if rank<=3:
                    for other in below:
                        if int(other['relevance_grade'])>=1:error('TOP3_POLLUTION',row,other)
                for other in below:
                    if int(other['relevance_grade'])==2:error('RELEVANCE_INVERSION',row,other)
                far=[r for r in below if int(r['relevance_grade'])==1 and r['rank']-rank>=3]
                if len(far)>=2:
                    for other in far:error('DEEP_LIST_INVERSION',row,other)
    names=[f'{m}@{k}' for m in ('precision','recall') for k in (1,3,5)]+['reciprocal_rank']+[f'ndcg@{k}' for k in (1,3,5,10)]
    def macro(jobs,key):
        vals=[r[key] for r in jobs if r[key] is not None]
        return statistics.mean(vals) if vals else None
    overall={('mrr' if k=='reciprocal_rank' else k):macro(per_job,k) for k in names}
    strict_jobs=[r['strict_grade2'] for r in per_job]
    strict={k:macro(strict_jobs,k) for k in strict_jobs[0] if k!='first_relevant_rank'}
    strict['contributing_queries']=sum(r['reciprocal_rank'] is not None for r in strict_jobs);strict['undefined_queries']=len(per_job)-strict['contributing_queries']
    top={str(k):{str(g):{'count':counts[g],'rate':counts[g]/(k*len(per_job))} for g in (0,1,2)} for k,counts in composition.items()}
    variance={key:{k:v for k,v in distribution([r[key] for r in per_job]).items() if k!='percentiles'}|{'min':min(r[key] for r in per_job),'max':max(r[key] for r in per_job)} for key in ('precision@3','recall@3','ndcg@5','ndcg@10')}
    bootstrap_jobs=bootstrap(per_job)
    ties={'exact_tie_groups':len(tie_groups),'tied_pairs':sum(n['size']*(n['size']-1)//2 for n in tie_groups),'jobs_affected':len({n['case'] for n in tie_groups}),'maximum_group_size':max((n['size'] for n in tie_groups),default=1)}
    return {'overall':overall,'per_job':per_job,'top_k_grade_composition':top,'variance':variance,'score_ties':ties,'strict_grade2':strict,'error_counts':{kind:sum(r['error_type']==kind for r in errors) for kind in ('TOP1_IRRELEVANT','GRADE2_BELOW_TOP3','GRADE2_BELOW_TOP5','TOP3_POLLUTION','RELEVANCE_INVERSION','DEEP_LIST_INVERSION')},
            'full_list':{'graded_inversions':sum(r['inversions'] for r in per_job),'relevant_below_top5':sum(int(r['relevance_grade'])>=1 and r['rank']>5 for r in predictions),'jobs_relevant_at_rank1':sum(r['first_relevant_rank']==1 for r in per_job),'jobs_grade2_at_rank1':composition[1][2]}},errors,bootstrap_jobs


def bootstrap(jobs,resamples=1000,seed=42):
    rng=random.Random(seed);names=['precision@3','recall@3','reciprocal_rank','ndcg@5','ndcg@10'];values={k:[] for k in names}
    for _ in range(resamples):
        sample=[rng.choice(jobs) for _ in jobs]
        for k in names:values[k].append(statistics.mean(r[k] for r in sample if r[k] is not None))
    def percentile(values,q):
        xs=sorted(values);p=(len(xs)-1)*q;lo=math.floor(p);hi=math.ceil(p)
        return xs[lo]+(xs[hi]-xs[lo])*(p-lo)
    return {'unit':'job','seed':seed,'resamples':resamples,'intervals':{('mrr' if k=='reciprocal_rank' else k):{'low':percentile(v,.025),'high':percentile(v,.975)} for k,v in values.items()}}


def random_sanity(predictions,simulations=10000,seed=42):
    groups=defaultdict(list)
    for r in predictions:groups[r['ranking_case_id']].append(int(r['relevance_grade']))
    rng=random.Random(seed);sums=defaultdict(float)
    for _ in range(simulations):
        values=[]
        for _,grades in sorted(groups.items()):
            shuffled=grades.copy();rng.shuffle(shuffled);values.append(pool_metrics(shuffled))
        for k in values[0]:
            if k!='first_relevant_rank':sums[k]+=statistics.mean(v[k] for v in values)
    return {'name':'random ranking sanity baseline','simulations':simulations,'seed':seed,'macro_expectation':{('mrr' if k=='reciprocal_rank' else k):v/simulations for k,v in sums.items()}}
