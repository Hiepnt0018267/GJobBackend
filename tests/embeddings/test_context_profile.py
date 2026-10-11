import asyncio
import json
from types import SimpleNamespace
import httpx
import pytest
from app.embeddings.ollama_provider import OllamaEmbeddingProvider
from app.embeddings.exceptions import EmbeddingInputTooLongError
from app.embeddings.profile import embedding_profile,profile_fingerprint
from app.embeddings.factory import get_embedding_provider
from app.services.cv_job_match_service import CVJobMatchService
from app.services.semantic_matching_service import cosine_similarity
from evaluation.run_ranking_semantic import verify_hashes
from pathlib import Path


def provider(context):
    def fake_runtime(request):
        data=json.loads(request.content);count=len(data['input'][0].split())
        assert data['truncate'] is False
        if count>data['options']['num_ctx']:
            return httpx.Response(400,json={'error':'input length exceeds context length'})
        return httpx.Response(200,json={'model':'bge-m3','embeddings':[[1.,0.]],'prompt_eval_count':count})
    return OllamaEmbeddingProvider(base_url='http://mock.invalid',model='bge-m3',timeout_seconds=30,num_ctx=context,transport=httpx.MockTransport(fake_runtime))


def test_actual_mock_token_admission_no_character_final_guard():
    # Synthetic runtime tokenizer:one whitespace-delimited token=one mock token.
    text='token '*5000
    with pytest.raises(EmbeddingInputTooLongError):asyncio.run(provider(4096).embed_many([text]))
    p=provider(8192);result=asyncio.run(p.embed_many([text]))
    assert p.last_prompt_eval_count==5000 and result.dimensions==2
    with pytest.raises(EmbeddingInputTooLongError):asyncio.run(p.embed_many(['token '*8193]))
    assert p.last_prompt_eval_count is None


def test_shared_profile_and_cache_identity_change_without_canonical_change(tmp_path):
    import hashlib
    original=b'synthetic frozen canonical professional input'
    (tmp_path/'canonical.json').write_bytes(original)
    p=get_embedding_provider();assert p.profile['num_ctx']==8192 and p.profile['truncate'] is False
    assert profile_fingerprint(embedding_profile('ollama','bge-m3',4096))!=profile_fingerprint(p.profile)
    with pytest.raises(ValueError):embedding_profile('ollama','bge-m3',16384)
    verify_hashes(tmp_path,{'canonical.json':hashlib.sha256(original).hexdigest()})
    assert (tmp_path/'canonical.json').read_bytes()==original
    assert cosine_similarity([1,0],[1,1])==pytest.approx(2**-.5)


def test_old_persisted_model_config_is_stale(monkeypatch):
    svc=CVJobMatchService(None,semantic_service=object(),expected_provider='ollama',expected_model='bge-m3')
    from app.services.baseline_matching_engine import BASELINE_MATCHING_VERSION
    from app.services.semantic_matching_service import SEMANTIC_MATCHING_VERSION
    row=SimpleNamespace(cv_fingerprint='cv',job_fingerprint='jd',baseline_engine_version=BASELINE_MATCHING_VERSION,semantic_engine_version=SEMANTIC_MATCHING_VERSION,embedding_provider='ollama',embedding_model_config='bge-m3',embedding_dimensions=1024)
    assert not svc._is_fresh(row,cv_fingerprint='cv',job_fingerprint='jd')
    row.embedding_model_config=svc.expected_model_config
    assert svc._is_fresh(row,cv_fingerprint='cv',job_fingerprint='jd')
