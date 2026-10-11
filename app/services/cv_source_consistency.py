"""Explicit post-failure source-authorized validation, never metadata-only waiver."""
import hashlib
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.partial_date import definitely_reversed
from app.schemas.source_date_consistency import (
    CONSISTENCY_VERSION,SourceDateConsistency,VerifiedSourceConflicts,conflict_binding,
)
from app.services.cv_date_evidence import ground_structured_dates
from app.services.cv_date_evidence import _ADAPTER
from app.services.cv_experience_alignment import align_experiences_to_source


def validate_source_grounded(source_text,payload):
    grounded,audit=ground_structured_dates(source_text,payload)
    source_hash=hashlib.sha256(source_text.encode()).hexdigest()
    proofs=[];conflicts=[]
    alignments=align_experiences_to_source(payload.get('experiences',[]),source_text)
    for alignment in alignments:
        index=alignment['experience_index'];pair=alignment['dates']
        if not definitely_reversed(*pair):continue
        if alignment['status']!='unique_ordered_assignment':
            raise ValueError('SOURCE_CONFLICT_ALIGNMENT_NOT_UNIQUE')
        for field,source_date in zip(('start_date','end_date'),pair):
            extracted=_ADAPTER.validate_python(payload['experiences'][index][field])
            if any(getattr(source_date,component,None) is not None and getattr(extracted,component,None)!=getattr(source_date,component,None)
                   for component in ('year','month','day')):
                raise ValueError('EXTRACTION_CONTRADICTION')
        item=grounded['experiences'][index]
        metadata=SourceDateConsistency(state='SOURCE_DATA_CONFLICT',source_sha256=source_hash,
                                       normalized_range_offsets=tuple(alignment['range_offsets']))
        item['date_consistency']=metadata.model_dump(mode='json')
        proofs.append(conflict_binding(item,metadata))
        conflicts.append({'experience_index':index,'state':metadata.state,'chronology_usable':False,
                          'range_offsets':alignment['range_offsets'],'source_sha256':source_hash,'rule_version':CONSISTENCY_VERSION})
    context={'source_conflict_proof':VerifiedSourceConflicts(frozenset(proofs))}
    result=StructuredCVExtractionResult.model_validate(grounded,context=context)
    return result,audit,conflicts,context


def validated_instance_context(result):
    bindings=set()
    for item in result.experiences:
        proof=item._source_conflict_proof
        if isinstance(proof,VerifiedSourceConflicts):bindings.update(proof.bindings)
    return {'source_conflict_proof':VerifiedSourceConflicts(frozenset(bindings))}
