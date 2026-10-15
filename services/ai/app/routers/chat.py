"""Streaming chat endpoint (SSE)."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models import ChatRequest, ErrorEvent
from app.sse import encode_sse

logger = logging.getLogger("veridoc.ai.chat")

router = APIRouter()


@router.post("/v1/chat/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """Stream a grounded answer as Server-Sent Events.

    The provider yields typed events; recoverable failures are surfaced as a
    terminal `error` event rather than an HTTP error, so the client always
    receives a well-formed stream.
    """
    provider = request.app.state.provider

    async def event_source() -> AsyncIterator[str]:
        try:
            async for event in provider.stream_chat(body):
                # Stop early if the client disconnected.
                if await request.is_disconnected():
                    logger.info("client disconnected; aborting stream")
                    return
                yield encode_sse(event)
        except Exception:  # pragma: no cover - defensive; mock cannot reach here
            logger.exception("inference stream failed")
            yield encode_sse(
                ErrorEvent(
                    message="The inference service encountered an internal error.",
                    code="inference_failed",
                )
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
