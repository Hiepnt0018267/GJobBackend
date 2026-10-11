"""Offline-capable shared deterministic alignment; no model, DB or ranking inputs.

Frozen generic policy: ordered one-to-one assignment of local role/range headers.
Score=6*role coverage +2*company coverage +3*responsibility coverage +date
compatibility, each component integer 0..1000. No per-document tuning.
"""
import re
import unicodedata
from functools import lru_cache
from app.services.cv_date_evidence import _RANGE, _normalized, _ADAPTER, _CURRENT
from app.schemas.partial_date import OpenEndedDate

ALIGNMENT_VERSION = 'cv-composite-monotonic-alignment-v1'
_LEGAL = {'ltd','limited','inc','incorporated','llc','corp','corporation','co'}
_STOP = {'the','a','an','and','of','to','in','for','with','on','as','at','by'}


def tokens(value):
    return re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',value or '').casefold())


def company_tokens(value):
    result=tokens(value)
    while result and result[-1] in _LEGAL:
        result.pop()
    return set(result)


def phrase_pattern(value):
    parts=tokens(value)
    return r'(?<!\w)'+r'[\W_]+'.join(re.escape(t) for t in parts)+r'(?!\w)' if parts else r'(?!)'


def _date_pair(match):
    start=_ADAPTER.validate_python(match['start'])
    end=OpenEndedDate(state='current') if re.fullmatch(_CURRENT,match['end'],re.I) else _ADAPTER.validate_python(match['end'])
    return start,end


def _coverage(wanted,available):
    return 1000*len(wanted & available)//len(wanted) if wanted else 0


def source_candidates(experiences,source_text):
    text=_normalized(source_text);candidates=[]
    role_hits=[]
    for item in experiences:
        role=item.get('position') or ''
        role_hits.extend((hit,role) for hit in re.finditer(phrase_pattern(role),text))
    for match in _RANGE.finditer(text):
        nearby=[(hit,role) for hit,role in role_hits
                if max(hit.start()-match.end(),match.start()-hit.end(),0)<=64
                and not re.search(r'\b(?:education|certificates|certifications|projects)\s+(?:\d{4}|bachelor|master|university|associate|high school)',
                                  text[min(hit.end(),match.end()):max(hit.start(),match.start())+8])]
        if not nearby:
            continue
        # Use nearest header hit only to delimit the span, never to assign records.
        hit,role=min(nearby,key=lambda pair:(max(pair[0].start()-match.end(),match.start()-pair[0].end(),0),-len(tokens(pair[1])),pair[0].start()))
        head_start=min(hit.start(),match.start());head_end=max(hit.end(),match.end())
        candidates.append({'start':head_start,'header_end':head_end,'range':match,
                           'role':role,'dates':_date_pair(match)})
    candidates.sort(key=lambda c:c['start'])
    # A source header may contain repeated date wording; require distinct ranges.
    if len({c['range'].span() for c in candidates})!=len(candidates):
        raise ValueError('ALIGNMENT_DUPLICATE_SOURCE_RANGE')
    for index,c in enumerate(candidates):
        end=candidates[index+1]['start'] if index+1<len(candidates) else len(text)
        # Do not let final work span absorb a later academic section.
        tail=text[c['header_end']:end]
        boundary=re.search(r'\beducation(?: and training)?\s+(?:\d{4}|bachelor|master|university|associate|high school)',tail)
        if boundary:end=c['header_end']+boundary.start()
        c['end']=end;c['body']=text[c['start']:end]
        c['header']=text[c['start']:min(end,c['header_end']+180)]
    return candidates


def _score(item,candidate):
    role=set(tokens(item.get('position')));actual=set(tokens(candidate['role']))
    role_score=_coverage(role,actual)
    # Avoid losing seniority when a shorter title is also a source substring.
    if role!=actual:
        role_score=min(role_score,1000*len(role & actual)//max(len(role|actual),1))
    if role_score<750:
        return None
    company=_coverage(company_tokens(item.get('company_name')),set(tokens(candidate['header'])))
    responsibilities=set(tokens(item.get('description')))-_STOP
    responsibility=_coverage(responsibilities,set(tokens(candidate['body']))-_STOP)
    if len(responsibilities)>=4 and responsibility<400:
        return None
    date_score=0
    for field,source_date in zip(('start_date','end_date'),candidate['dates']):
        value=item.get(field)
        if value is None:continue
        try:extracted=_ADAPTER.validate_python(value)
        except (ValueError,TypeError):continue
        if isinstance(source_date,OpenEndedDate):
            date_score+=500 if isinstance(extracted,OpenEndedDate) or item.get('is_current') else 0
        elif not isinstance(extracted,OpenEndedDate):
            date_score+=500 if extracted.year==source_date.year else 0
    # Company mismatch needs strong independent local responsibility evidence.
    if company==0 and responsibility<400:
        return None
    return 6*role_score+2*company+3*responsibility+date_score,{
        'role':role_score,'company':company,'responsibilities':responsibility,'dates':date_score}


def align_experiences_to_source(experiences,source_text):
    if not experiences:return []
    candidates=source_candidates(experiences,source_text)
    scores=[[_score(item,c) for c in candidates] for item in experiences]
    # Top two global monotonic assignments expose competing optimal paths.
    @lru_cache(None)
    def solve(i,j):
        if i==len(experiences):return ((0,(),False),)
        if len(candidates)-j<len(experiences)-i:return ()
        paths=[]
        for k in range(j,len(candidates)):
            value=scores[i][k]
            if value is None:continue
            for total,path,equivalent in solve(i+1,k+1):paths.append((value[0]+total,(k,)+path,equivalent))
        # Retain two DISTINCT date outcomes, not just the first two paths: many
        # equivalent paths must not hide a third tied path with different dates.
        grouped={}
        for total,path,equivalent in sorted(paths,key=lambda v:(-v[0],v[1])):
            signature=tuple(tuple(d.model_dump_json() if hasattr(d,'model_dump_json') else d.isoformat() for d in candidates[k]['dates']) for k in path)
            key=(total,signature)
            if key in grouped:
                prior=grouped[key];grouped[key]=(prior[0],prior[1],True)
            else:grouped[key]=(total,path,equivalent)
        return tuple(sorted(grouped.values(),key=lambda v:(-v[0],v[1]))[:2])
    best=solve(0,0)
    if not best:raise ValueError('ALIGNMENT_NO_SAFE_ORDERED_ASSIGNMENT')
    tied=len(best)>1 and best[0][0]==best[1][0]
    if tied:
        def outcomes(path):
            return tuple(tuple(d.model_dump_json() if hasattr(d,'model_dump_json') else d.isoformat() for d in candidates[k]['dates']) for k in path)
        if outcomes(best[0][1])!=outcomes(best[1][1]):
            raise ValueError('ALIGNMENT_AMBIGUOUS_DISTINCT_DATES')
    result=[]
    for i,k in enumerate(best[0][1]):
        c=candidates[k]
        result.append({'experience_index':i,'source_span':[c['start'],c['end']],
                       'range_offsets':list(c['range'].span()),'source_candidate_index':k,
                       'status':'equivalent_date_tie' if best[0][2] else 'unique_ordered_assignment',
                       'components':scores[i][k][1],'score':scores[i][k][0],
                       'dates':c['dates']})
    return result
