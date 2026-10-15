"""OpenAICompatibleProvider against an in-process fake OpenAI server."""
from __future__ import annotations

import httpx
import pytest

from app.models import ChatRequest
from app.providers.base import ChatMessage, InferenceError
from app.providers.openai_compatible import OpenAICompatibleProvider
from tests.fake_openai import make_fake_openai_app


def _provider(model: str) -> OpenAICompatibleProvider:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=make_fake_openai_app()),
        base_url="http://fake",
    )
    return OpenAICompatibleProvider(base_url="http://fake/v1", model=model, client=client)


async def test_generate_success() -> None:
    result = await _provider("echo").generate(
        [ChatMessage(role="user", content="q")], max_tokens=64, temperature=0.0
    )
    assert "[E1]" in result.text
    assert result.model == "echo"
    assert result.token_count > 0


async def test_generate_upstream_error() -> None:
    with pytest.raises(InferenceError) as ei:
        await _provider("boom").generate(
            [ChatMessage(role="user", content="q")], max_tokens=64, temperature=0.0
        )
    assert ei.value.code == "inference_upstream_error"


async def test_generate_malformed_response() -> None:
    with pytest.raises(InferenceError) as ei:
        await _provider("garbage").generate(
            [ChatMessage(role="user", content="q")], max_tokens=64, temperature=0.0
        )
    assert ei.value.code == "inference_malformed"


async def test_generate_connection_failure() -> None:
    # No ASGI app: a real connection attempt to an unroutable address fails.
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:0/v1", model="echo", timeout_s=1.0
    )
    try:
        with pytest.raises(InferenceError) as ei:
            await provider.generate(
                [ChatMessage(role="user", content="q")], max_tokens=16, temperature=0.0
            )
        assert ei.value.code in {"inference_unavailable", "inference_timeout"}
    finally:
        await provider.aclose()  # provider owns its client; close it


async def test_stream_chat_yields_tokens_then_done() -> None:
    events = [
        e async for e in _provider("echo").stream_chat(ChatRequest(message="hi"))
    ]
    types = [e.type for e in events]
    assert types[0] == "token"
    assert types[-1] == "done"
    done = events[-1]
    assert done.mock is False  # real provider, not mock


async def test_stream_chat_surfaces_upstream_error() -> None:
    events = [
        e async for e in _provider("boom").stream_chat(ChatRequest(message="hi"))
    ]
    assert events[-1].type == "error"
    assert events[-1].code == "inference_upstream_error"
