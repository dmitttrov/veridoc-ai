"""Hybrid retrieval endpoint (Phase 2).

Returns retrieved EVIDENCE passages. These are source excerpts, not
AI-generated answers.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models import RetrievalRequest, RetrievalResponse
from app.retrieval.service import retrieve as run_retrieve

router = APIRouter()


@router.post("/v1/retrieve", response_model=RetrievalResponse)
async def retrieve(request: Request, body: RetrievalRequest) -> RetrievalResponse:
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Database is not available."},
        )
    return await run_retrieve(pool, request.app.state.embedder, body)
