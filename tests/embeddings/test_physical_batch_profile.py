import asyncio
import json
import httpx
import pytest
from app.embeddings.factory import get_embedding_provider
from app.embeddings.ollama_provider import OllamaEmbeddingProvider
from app.embeddings.profile import embedding_profile,profile_fingerprint
from app.embeddings.exceptions import EmbeddingInputTooLongError
from evaluation.embedding_admission_gate import validate_admission
from evaluation.common import EvaluationDataError


def test_shared_batch_request_and_profile_fingerprint():
    profile=get_embedding_provider().profile
    assert profile['num_ctx']==8192 and profile['num_batch']==4096 and profile['truncate'] is False
    assert profile_fingerprint(profile)!=profile_fingerprint(embedding_profile('ollama','bge-m3',8192,2048))
    requests=[]
    def handler(request):
        data=json.loads(request.content);requests.append(data);count=len(data['input'][0].split())
        assert data['options']=={'num_ctx':8192,'num_batch':4096} and data['truncate'] is False
        if count>4096:return httpx.Response(400,json={'error':'the input length exceeds the context length'})
        return httpx.Response(200,json={'model':'bge-m3','embeddings':[[1,0]],'prompt_eval_count':count})
    p=OllamaEmbeddingProvider(base_url='http://mock.invalid',model='bge-m3',timeout_seconds=30,transport=httpx.MockTransport(handler))
    asyncio.run(p.embed_many(['token '*2076]))
    with pytest.raises(EmbeddingInputTooLongError):asyncio.run(p.embed_many(['token '*4097]))
    assert requests[0]['input'][0]=='token '*2076
    with pytest.raises(ValueError):embedding_profile('ollama','bge-m3',8192,8192)


def test_runtime_flags_and_exact_count_hard_stop():
    flags={'-c':8192,'-b':4096,'-ub':4096}
    assert validate_admission(flags,[{'count':2076},{'count':2365}],get_embedding_provider().profile)['maximum_total_tokens']==2365
    with pytest.raises(EvaluationDataError):validate_admission(dict(flags,**{'-ub':2048}),[],get_embedding_provider().profile)
    with pytest.raises(EvaluationDataError):validate_admission(flags,[{'count':4097}],get_embedding_provider().profile)
