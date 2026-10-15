"""Grounded RAG endpoint (SSE).

Safety model for streaming: the model's response is **fully generated and its
citations verified BEFORE anything is streamed to the client**. Only the
verified answer is then streamed token-by-token. This guarantees the client
never sees unverified or fabricated-citation content presented as a final
answer. It trades first-token latency for correctness — the right trade for a
verifiability-first product.
"""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models import CitationsEvent, DoneEvent, ErrorEvent, RagRequest, TokenEvent
from app.providers.base import InferenceError
from app.rag.service import answer_question
from app.sse import encode_sse

logger = logging.getLogger("veridoc.ai.rag")

router = APIRouter()

_TOKEN = re.compile(r"\S+\s*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text)


@router.post("/v1/rag/answer")
async def rag_answer(request: Request, body: RagRequest) -> StreamingResponse:
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Database is not available."},
        )

    settings = request.app.state.settings
    provider = request.app.state.provider

    async def event_source() -> AsyncIterator[str]:
        try:
            outcome = await answer_question(
                pool,
                request.app.state.embedder,
                request.app.state.reranker,
                provider,
                settings,
                question=body.question,
                document_ids=body.document_ids,
                top_k=body.top_k,
                rerank=body.rerank,
            )
        except InferenceError as exc:
            # NEVER fall back to the mock: surface the failure explicitly.
            logger.warning("rag inference failed code=%s", exc.code)
            yield encode_sse(ErrorEvent(message=exc.message, code=exc.code))
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("rag pipeline error")
            yield encode_sse(
                ErrorEvent(message="The assistant encountered an error.", code="rag_failed")
            )
            return

        # Stream the already-verified answer.
        tokens = _tokenize(outcome.answer)
        for token in tokens:
            if await request.is_disconnected():
                return
            yield encode_sse(TokenEvent(text=token))

        if outcome.citations:
            yield encode_sse(CitationsEvent(citations=outcome.citations))

        yield encode_sse(
            DoneEvent(
                mock=outcome.mock,
                model=outcome.model,
                token_count=len(tokens),
                abstained=outcome.abstained,
                invalid_citation_count=outcome.invalid_citation_count,
            )
        )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
