"""Shared full-input embedding capacity identity; no algorithm normalization."""
import hashlib
import json

EMBEDDING_PROFILE_VERSION='full-input-context-batch-v2'


def embedding_profile(provider,model,num_ctx,num_batch=4096):
    if isinstance(num_ctx,bool) or not isinstance(num_ctx,int) or not 1024<=num_ctx<=8192:
        raise ValueError('Embedding context must be1024..8192')
    if isinstance(num_batch,bool) or not isinstance(num_batch,int) or not 1024<=num_batch<=4096:
        raise ValueError('Embedding batch must be1024..4096')
    return {'version':EMBEDDING_PROFILE_VERSION,'provider':provider,'model':model,
            'num_ctx':num_ctx,'num_batch':num_batch,'truncate':False,'vector_postprocessing':'none'}


def profile_fingerprint(profile):
    return hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()
