"""A tiny fake OpenAI-compatible server for integration tests.

Behaviour is selected by the requested ``model`` so a single app can exercise
success, abstention, fabricated citations, upstream errors, and malformed
responses — for both buffered and streaming requests. No network, no real model.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


def _completion(content: str) -> dict[str, Any]:
    return {
        "id": "cmpl-fake",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"completion_tokens": len(content.split())},
    }


def _content_for(model: str) -> str:
    if model == "abstain":
        return "INSUFFICIENT_EVIDENCE"
    if model == "fabricate":
        return "According to the filing the answer is 10 [E9]."
    # default "echo": a grounded-looking answer citing the first evidence marker
    return "Based on the evidence, the figure is reported on the cited page [E1]."


def make_fake_openai_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):  # type: ignore[no-untyped-def]
        payload = await request.json()
        model = payload.get("model", "echo")
        stream = bool(payload.get("stream"))

        if model == "boom":
            return JSONResponse({"error": "internal"}, status_code=500)
        if model == "garbage":
            return JSONResponse({"unexpected": "shape"})  # missing choices

        content = _content_for(model)

        if not stream:
            return JSONResponse(_completion(content))

        async def sse() -> AsyncIterator[bytes]:
            for word in content.split(" "):
                chunk = {
                    "choices": [{"index": 0, "delta": {"content": word + " "}}]
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    return app
