import asyncio
import json
import httpx
import pytest
from app.embeddings.ollama_provider import OllamaEmbeddingProvider
from app.embeddings.exceptions import EmbeddingInputTooLongError,EmbeddingInputError
from evaluation.token_admission_diagnostics import DiagnosticTransport,safe_error_metadata,runtime_token_count


def test_error_origin_http_and_no_text_logging(caplog):
    secret='synthetic private@example.com secret'
    transport=DiagnosticTransport(httpx.MockTransport(lambda r:httpx.Response(400,json={'error':'the input length exceeds the context length'})),secret)
    provider=OllamaEmbeddingProvider(base_url='http://mock.invalid',model='bge-m3',timeout_seconds=30,num_ctx=8192,transport=transport)
    with pytest.raises(EmbeddingInputTooLongError):asyncio.run(provider.embed_many([secret]))
    assert transport.calls==1 and transport.response_metadata['http_status']==400
    assert transport.request_metadata['input_count']==1 and transport.request_metadata['num_ctx']==8192
    assert secret not in json.dumps([transport.request_metadata,transport.response_metadata]) and secret not in caplog.text
    with pytest.raises(AssertionError):asyncio.run(provider.embed_many([secret]))


def test_unknown_error_message_is_redacted_and_empty_input_local_not_length():
    metadata=safe_error_metadata(httpx.Response(400,json={'error':'CV belongs to private@example.com','private@example.com':'secret'}))
    assert 'private@' not in json.dumps(metadata)
    provider=OllamaEmbeddingProvider(base_url='http://mock.invalid',model='bge-m3',timeout_seconds=30,transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError())))
    with pytest.raises(EmbeddingInputError):asyncio.run(provider.embed_many([' ']))


def test_exact_runtime_token_endpoint_shape_and_counts_only():
    def handler(request):
        data=json.loads(request.content);assert data['content']=='synthetic'
        return httpx.Response(200,json={'tokens':[0,11,12,2] if data['add_special'] else [11,12]})
    with httpx.Client(base_url='http://mock.invalid',transport=httpx.MockTransport(handler)) as client:
        assert runtime_token_count(client,'synthetic')['count']==2
        assert runtime_token_count(client,'synthetic',add_special=True)=={'count':4,'add_special':True,'starts_bos':True,'ends_eos':True}
