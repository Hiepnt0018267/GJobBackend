"""Private opt-in raw response retention. Never a canonical benchmark artifact."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from evaluation.prepare_ranking_canonical import atomic_json


class PrivateStructuredCheckpoint:
    def __init__(self,path,identity):
        self.path=Path(path)
        self.identity=dict(identity)

    def start_generation(self):
        if self.path.exists():
            raise RuntimeError('PRIVATE_GENERATION_ALREADY_STARTED_USE_STORED_PAYLOAD')
        atomic_json(self.path,{**self.identity,'timestamp':datetime.now(timezone.utc).isoformat(),
                              'generation_count':1,'validation_status':'GENERATION_STARTED'})

    def capture(self,content,metrics):
        record=json.loads(self.path.read_text(encoding='utf-8'))
        if 'raw_structured_response' in record:
            raise RuntimeError('SECOND_RESPONSE_FORBIDDEN')
        record.update(raw_structured_response=content,
                      generation_metadata=asdict(metrics) if metrics else None,
                      response_timestamp=datetime.now(timezone.utc).isoformat(),
                      validation_status='RECEIVED_BEFORE_VALIDATION')
        atomic_json(self.path,record)

    def result(self,status,diagnostic=None):
        record=json.loads(self.path.read_text(encoding='utf-8'))
        record.update(validation_status=status,validation_diagnostic=diagnostic)
        atomic_json(self.path,record)

    def payload(self):
        record=json.loads(self.path.read_text(encoding='utf-8'))
        for key,value in self.identity.items():
            if record.get(key)!=value:
                raise RuntimeError('PRIVATE_SOURCE_IDENTITY_MISMATCH')
        return json.loads(record['raw_structured_response'])
