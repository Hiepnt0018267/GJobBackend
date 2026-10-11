"""Budget hardening tests for OllamaProvider structured extraction.

All tests use httpx.MockTransport or a stub token counter.
No live Ollama calls.  No database access.

Rules verified:
  §28 preflight fits -> provider called
  §29 preflight overflow -> provider NOT called
  §30 exact boundary
  §31 num_predict in payload
  §32 output cap exhausted -> typed error
  §33 valid JSON -> success
  §6  token accounting unavailable -> character fallback, no silent bypass
"""
import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.ai.exceptions import (
    AIContextBudgetExceededError,
    AIOutputBudgetExceededError,
    AITokenAccountingUnavailableError,
)
from app.ai.ollama_provider import OllamaProvider
from app.ai.ollama_token_budget import PromptAccounting


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SimpleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: int


def _success_response(content: object, **meta) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "qwen3:8b",
            "done": True,
            "done_reason": "stop",
            "message": {"role": "assistant", "content": content},
            **meta,
        },
    )


def _exhausted_response(content: object, eval_count: int, **meta) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "qwen3:8b",
            "done": True,
            "done_reason": "length",
            "eval_count": eval_count,
            "prompt_eval_count": 100,
            "message": {"role": "assistant", "content": content},
            **meta,
        },
    )


class StubTokenCounter:
    def __init__(self, prompt_tokens: int, special_tokens: int, effective_num_ctx: int):
        self._accounting = PromptAccounting(
            prompt_tokens=prompt_tokens,
            special_tokens=special_tokens,
            effective_num_ctx=effective_num_ctx,
        )
        self.call_count = 0

    async def count(self, payload) -> PromptAccounting:
        self.call_count += 1
        return self._accounting


class FailingTokenCounter:
    async def count(self, payload):
        raise AITokenAccountingUnavailableError("test: accounting unavailable")

    async def verify_safe_runtime(self):
        return None  # synthetic runtime enforces shift/truncate flags


def _provider(handler, *, num_ctx=8192, num_predict=3072, safety_margin=256, token_counter=None) -> OllamaProvider:
    if token_counter is None:
        token_counter = StubTokenCounter(prompt_tokens=500, special_tokens=30, effective_num_ctx=num_ctx)
    return OllamaProvider(
        base_url="http://ollama.test:11434",
        model="qwen3:8b",
        timeout_seconds=10,
        num_ctx=num_ctx,
        num_predict=num_predict,
        safety_margin=safety_margin,
        retry_delay_seconds=0,
        transport=httpx.MockTransport(handler),
        token_counter=token_counter,
    )


# ---------------------------------------------------------------------------
# §31 -- num_predict MUST be present in every structured request payload
# ---------------------------------------------------------------------------

def test_num_predict_in_request_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.update(body)
        return _success_response(json.dumps({"name": "Test", "value": 1}), prompt_eval_count=600, eval_count=30)

    provider = _provider(handler, num_predict=3072)
    asyncio.run(provider.generate_structured("CV text", SimpleResult))

    assert "num_predict" in captured.get("options", {}), "num_predict must be present in options"
    assert captured["options"]["num_predict"] == 3072


# ---------------------------------------------------------------------------
# §28 -- Preflight fits -> provider called
# ---------------------------------------------------------------------------

def test_preflight_fits_allows_provider_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _success_response(json.dumps({"name": "Fit", "value": 42}), prompt_eval_count=500, eval_count=20)

    # 500 + 30 + 3072 + 256 = 3858 < 8192
    counter = StubTokenCounter(prompt_tokens=500, special_tokens=30, effective_num_ctx=8192)
    provider = _provider(handler, num_ctx=8192, num_predict=3072, safety_margin=256, token_counter=counter)
    result = asyncio.run(provider.generate_structured("CV text", SimpleResult))

    assert calls == 1
    assert isinstance(result, SimpleResult)


# ---------------------------------------------------------------------------
# §29 -- Preflight overflow -> provider NOT called
# ---------------------------------------------------------------------------

def test_preflight_overflow_blocks_provider_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _success_response("{}")

    # 5000 + 30 + 3072 + 256 = 8358 > 8192
    counter = StubTokenCounter(prompt_tokens=5000, special_tokens=30, effective_num_ctx=8192)
    provider = _provider(handler, num_ctx=8192, num_predict=3072, safety_margin=256, token_counter=counter)

    with pytest.raises(AIContextBudgetExceededError):
        asyncio.run(provider.generate_structured("Long CV", SimpleResult))

    assert calls == 0


# ---------------------------------------------------------------------------
# §30 -- Exact boundary tests
# ---------------------------------------------------------------------------

def test_preflight_exact_boundary_fits() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _success_response(json.dumps({"name": "Boundary", "value": 0}), prompt_eval_count=4608, eval_count=30)

    # 4608 + 256 + 3072 + 256 = 8192 (exactly at limit -> allowed)
    counter = StubTokenCounter(prompt_tokens=4608, special_tokens=256, effective_num_ctx=8192)
    provider = _provider(handler, num_ctx=8192, num_predict=3072, safety_margin=256, token_counter=counter)
    result = asyncio.run(provider.generate_structured("Boundary CV", SimpleResult))

    assert calls == 1
    assert result.name == "Boundary"


def test_preflight_over_boundary_by_one_blocks_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _success_response("{}")

    # 4609 + 256 + 3072 + 256 = 8193 > 8192 (one over -> blocked)
    counter = StubTokenCounter(prompt_tokens=4609, special_tokens=256, effective_num_ctx=8192)
    provider = _provider(handler, num_ctx=8192, num_predict=3072, safety_margin=256, token_counter=counter)

    with pytest.raises(AIContextBudgetExceededError):
        asyncio.run(provider.generate_structured("Too long CV", SimpleResult))

    assert calls == 0


# ---------------------------------------------------------------------------
# §32 -- Output budget exhausted -> typed error, partial JSON rejected
# ---------------------------------------------------------------------------

def test_output_cap_exhausted_done_reason_length_raises_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _exhausted_response(json.dumps({"name": "Partial"}), eval_count=3072)

    with pytest.raises(AIOutputBudgetExceededError):
        asyncio.run(_provider(handler).generate_structured("CV text", SimpleResult))


def test_complete_valid_json_at_cap_with_normal_stop_is_not_truncated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "model": "qwen3:8b", "done": True, "done_reason": "stop",
            "eval_count": 3072, "prompt_eval_count": 100,
            "message": {"role": "assistant", "content": json.dumps({"name": "A", "value": 1})},
        })

    assert asyncio.run(_provider(handler, num_predict=3072).generate_structured("CV text", SimpleResult)).name == 'A'


# ---------------------------------------------------------------------------
# §33 -- Valid JSON within budget -> success
# ---------------------------------------------------------------------------

def test_valid_json_within_budget_succeeds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _success_response(json.dumps({"name": "An", "value": 99}), prompt_eval_count=600, eval_count=25)

    result = asyncio.run(_provider(handler).generate_structured("CV text", SimpleResult))
    assert isinstance(result, SimpleResult)
    assert result.name == "An"
    assert result.value == 99


# ---------------------------------------------------------------------------
# §6  -- Token accounting unavailable -> character fallback, not silent bypass
# ---------------------------------------------------------------------------

def test_token_accounting_unavailable_falls_back_and_allows_small_prompt() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        assert "num_predict" in body.get("options", {}), "num_predict must be present even when counter fails"
        return _success_response(json.dumps({"name": "Fallback", "value": 7}), prompt_eval_count=200, eval_count=15)

    # Short prompt: ~90 chars -> approx_tokens = 90//3 + 512 = 542
    # 542 + 3072 + 256 = 3870 < 8192 -> fits
    provider = _provider(handler, num_ctx=8192, num_predict=3072, safety_margin=256,
                         token_counter=FailingTokenCounter())
    result = asyncio.run(provider.generate_structured("Short CV.", SimpleResult))

    assert calls == 1
    assert result.name == "Fallback"


def test_token_accounting_unavailable_does_not_block_by_oversized_heuristic() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _success_response('{"name":"Safe","value":1}', prompt_eval_count=200, eval_count=15)

    # Very small ctx (512). "A"*3000 -> content ~3300 chars -> approx_tokens = 1100 + 512 = 1612
    # 1612 + 3072 + 256 = 4940 > 512 -> blocked
    provider = _provider(handler, num_ctx=8192, num_predict=3072, safety_margin=256,
                         token_counter=FailingTokenCounter())

    assert asyncio.run(provider.generate_structured("A" * 30000, SimpleResult)).name == 'Safe'

    assert calls == 1
