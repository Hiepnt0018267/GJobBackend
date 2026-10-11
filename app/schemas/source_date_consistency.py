"""Source conflict metadata is NOT authority to bypass request validation."""
import hashlib
import json
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from app.schemas.partial_date import CVDate

CONSISTENCY_VERSION = 'cv-source-date-consistency-v1'


class SourceDateConsistency(BaseModel):
    model_config=ConfigDict(extra='forbid')
    state: Literal['SOURCE_DATA_CONFLICT']
    chronology_usable: Literal[False] = False
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    normalized_range_offsets: tuple[int,int]
    rule_version: Literal['cv-source-date-consistency-v1'] = CONSISTENCY_VERSION


def conflict_binding(record,metadata):
    data={key:(record.get(key).strip() or None) if isinstance(record.get(key),str) else record.get(key)
          for key in ('company_name','position','description')}
    for field in ('start_date','end_date'):
        value=TypeAdapter(CVDate).validate_python(record[field])
        data[field]=value.model_dump(mode='json') if hasattr(value,'model_dump') else value.isoformat()
    data['metadata']=metadata.model_dump(mode='json')
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class VerifiedSourceConflicts:
    """Internal in-process capability, generated only after source verification."""
    bindings: frozenset[str]

    def allows(self,record,metadata):
        return metadata is not None and conflict_binding(record,metadata) in self.bindings
