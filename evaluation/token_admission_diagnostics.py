"""Safe opt-in diagnostics. No automatic request, generation or config mutation."""
import hashlib
import json
import httpx

_KNOWN_ERRORS={
    'the input length exceeds the context length',
    'input length exceeds context length',
    'input length exceeds maximum context length',
}


def safe_error_metadata(response):
    try:payload=response.json()
    except ValueError:payload={}
    message=payload.get('error') if isinstance(payload,dict) else None
    allowed={'error','model','prompt_eval_count','total_duration','load_duration','embeddings','usage','data'}
    return {'http_status':response.status_code,'response_fields':sorted(k if k in allowed else '[unknown field redacted]' for k in payload) if isinstance(payload,dict) else [],
            'error_message':message if message in _KNOWN_ERRORS else '[unrecognized provider error redacted]',
            'error_json_type':type(message).__name__}


class DiagnosticTransport(httpx.AsyncBaseTransport):
    def __init__(self,transport,expected_text):
        self.transport=transport;self.expected_sha=hashlib.sha256(expected_text.encode()).hexdigest()
        self.calls=0;self.request_metadata=None;self.response_metadata=None

    async def handle_async_request(self,request):
        if self.calls:raise AssertionError('DIAGNOSTIC_REQUEST_BUDGET_EXHAUSTED')
        data=json.loads(request.content);inputs=data.get('input')
        if not isinstance(inputs,list) or len(inputs)!=1 or hashlib.sha256(inputs[0].encode()).hexdigest()!=self.expected_sha:
            raise AssertionError('DIAGNOSTIC_INPUT_CHANGED')
        if request.url.path!='/api/embed' or data.get('truncate') is not False or data.get('options',{}).get('num_ctx')!=8192:
            raise AssertionError('DIAGNOSTIC_PROFILE_CHANGED')
        self.calls+=1
        self.request_metadata={'input_count':1,'canonical_text_sha256':self.expected_sha,
                               'input_exactly_unchanged':True,'model':data.get('model'),
                               'num_ctx':8192,'truncate':False,'top_level_keys':sorted(data)}
        response=await self.transport.handle_async_request(request)
        await response.aread();self.response_metadata=safe_error_metadata(response)
        return response

    async def aclose(self):await self.transport.aclose()


def runtime_token_count(client,text,*,add_special=False):
    """Exact loaded runner /tokenize path, matching Ollama v0.34.2 request."""
    response=client.post('/tokenize',json={'content':text,'add_special':add_special})
    response.raise_for_status();tokens=response.json()['tokens']
    if not isinstance(tokens,list) or any(isinstance(v,bool) or not isinstance(v,int) for v in tokens):
        raise ValueError('INVALID_RUNTIME_TOKEN_IDS')
    return {'count':len(tokens),'add_special':add_special,
            'starts_bos':bool(tokens and tokens[0]==0),'ends_eos':bool(tokens and tokens[-1]==2)}
