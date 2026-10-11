"""Deterministic local date-range evidence, independent of labels/models/DB."""
import copy
import re
from pydantic import TypeAdapter
from app.schemas.partial_date import CVDate, OpenEndedDate, PartialDate

EVIDENCE_CONTRACT_VERSION = "cv-local-date-range-evidence-v2-composite"
_MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
_DATE = r'(?:\d{4}-\d{2}-\d{2}|'+_MONTH+r'\.?\s+\d{4}|\d{1,2}/\d{4}|\d{4}-\d{1,2}|(?:19|20)\d{2})'
_CURRENT = r'(?:Present|Current|Now|Till\s+date)'
_RANGE = re.compile(r'(?<!\w)(?P<start>'+_DATE+r')\s*(?:to|[-–—])\s*(?P<end>'+_DATE+'|'+_CURRENT+r')(?!\w)', re.I)
_ADAPTER = TypeAdapter(CVDate)


def _normalized(text):
    return ' '.join(text.casefold().split())


def resolve_date_evidence(source_text, record, *, anchor_field, secondary_field):
    """Require a unique adjacent range + record anchor, not a global year match.

    Conservative admission: multiple plausible local ranges are unresolved.
    Only metadata changes; raw/provider payload and professional fields stay intact.
    """
    text = _normalized(source_text)
    anchor = _normalized(record.get(anchor_field) or '')
    secondary = _normalized(record.get(secondary_field) or '')
    if len(anchor) < 4:
        raise ValueError('DATE_EVIDENCE_ANCHOR_MISSING')
    ranges = list(_RANGE.finditer(text))
    found = {}
    for hit in re.finditer(re.escape(anchor), text):
        for match in ranges:
            # Source resume headers normally put the range immediately before
            # or after the role. Do not traverse unrelated distant prose.
            gap = max(hit.start()-match.end(), match.start()-hit.end(), 0)
            if gap > 48:
                continue
            left,right = min(hit.start(),match.start()),max(hit.end(),match.end())
            context=text[max(0,left-40):min(len(text),right+160)]
            if secondary and secondary not in context:
                continue
            found[match.span()] = match
    if len(found) != 1:
        if not found:
            # A single adjacent source year without a range retains uncertainty
            # about its start/end interpretation, never a fabricated month/day.
            years=set()
            for hit in re.finditer(re.escape(anchor),text):
                local=text[max(0,hit.start()-48):hit.end()+80]
                if secondary and secondary not in text[max(0,hit.start()-80):hit.end()+160]:
                    continue
                years.update(int(x) for x in re.findall(r'\b(?:19|20)\d{2}\b',local))
            values=[record.get(k) for k in ('start_date','end_date') if record.get(k) is not None]
            parsed=[_ADAPTER.validate_python(v) for v in values]
            if len(years)==1 and parsed and all(not isinstance(v,OpenEndedDate) and v.year==next(iter(years)) for v in parsed):
                value=PartialDate(year=next(iter(years)),precision='ambiguous')
                return (value if record.get('start_date') is not None else None,
                        value if record.get('end_date') is not None else None,
                        {'status':'ambiguous_local_year','open_ended':False})
        raise ValueError('DATE_EVIDENCE_LOCAL_RANGE_UNRESOLVED')
    match = next(iter(found.values()))
    start = _ADAPTER.validate_python(match['start'])
    end = OpenEndedDate(state='current') if re.fullmatch(_CURRENT, match['end'], re.I) else _ADAPTER.validate_python(match['end'])
    return start,end,{'status':'verified_local_range','range_offsets':list(match.span()),'open_ended':isinstance(end,OpenEndedDate)}


def ground_structured_dates(source_text, payload):
    """Ground date metadata from local source ranges without editing other fields.

    Never guess/drop/swap dates or items. Missing date fields stay absent. Unsupported
    local alignments fail rather than accepting unrelated document-wide evidence.
    """
    if not isinstance(payload,dict):
        raise ValueError('STRUCTURED_OBJECT_REQUIRED')
    result=copy.deepcopy(payload);audit=[]
    # Import here to keep the shared token/date primitives free of circular imports.
    from app.services.cv_experience_alignment import align_experiences_to_source, phrase_pattern
    experiences=result.get('experiences',[])
    has_ranges=bool(_RANGE.search(source_text))
    if experiences and has_ranges:
        for alignment in align_experiences_to_source(experiences,source_text):
            item=experiences[alignment['experience_index']]
            # A source-correct range does not excuse generated reversed chronology.
            # Source-conflict approval is an explicit, separately verified operation.
            try:
                original_start=_ADAPTER.validate_python(item['start_date']) if item.get('start_date') is not None else None
                original_end=_ADAPTER.validate_python(item['end_date']) if item.get('end_date') is not None else None
            except ValueError:
                original_start=original_end=None
            from app.schemas.partial_date import definitely_reversed
            if definitely_reversed(original_start,original_end) and not definitely_reversed(*alignment['dates']):
                raise ValueError('EXTRACTION_CONTRADICTION')
            for field,value in zip(('start_date','end_date'),alignment['dates']):
                item[field]=value.model_dump(mode='json') if hasattr(value,'model_dump') else value.isoformat()
            item['is_current']=isinstance(alignment['dates'][1],OpenEndedDate)
            audit.append({'section':'experiences','index':alignment['experience_index'],
                          **{k:v for k,v in alignment.items() if k not in ('dates','experience_index')}})
    remaining=[('educations','school_name','degree'),('projects','name','role')]
    if experiences and not has_ranges:
        remaining.insert(0,('experiences','position','company_name'))
    for section,anchor,secondary in remaining:
        for index,item in enumerate(result.get(section,[])):
            if not isinstance(item,dict):
                raise ValueError('STRUCTURED_ITEM_REQUIRED')
            if item.get('start_date') is None and item.get('end_date') is None:
                continue
            try:
                start,end,evidence=resolve_date_evidence(source_text,item,anchor_field=anchor,secondary_field=secondary)
            except ValueError:
                # Unique institution + one locally supported year is enough for
                # explicit year ambiguity even when degree punctuation differs.
                text=_normalized(source_text);hits=list(re.finditer(phrase_pattern(item.get(anchor) or ''),text))
                years=set(re.findall(r'\b(?:19|20)\d{2}\b',text[max(0,hits[0].start()-128):hits[0].end()+64])) if len(hits)==1 else set()
                existing=[_ADAPTER.validate_python(item[k]) for k in ('start_date','end_date') if item.get(k) is not None]
                if len(years)!=1 or not existing or any(isinstance(v,OpenEndedDate) or str(v.year) not in years for v in existing):raise
                value=PartialDate(year=int(next(iter(years))),precision='ambiguous')
                start=value if item.get('start_date') is not None else None
                end=value if item.get('end_date') is not None else None
                evidence={'status':'ambiguous_unique_institution_local_year','open_ended':False}
            for name,value in [('start_date',start),('end_date',end)]:
                if value is None:
                    continue
                # No fabricated date: these are the exact adjacent source tokens.
                item[name]=value.model_dump(mode='json') if isinstance(value,(PartialDate,OpenEndedDate)) else value.isoformat()
            if section in ('experiences','educations') and isinstance(end,OpenEndedDate):
                item['is_current']=True
            audit.append({'section':section,'index':index,**evidence})
    return result,audit
