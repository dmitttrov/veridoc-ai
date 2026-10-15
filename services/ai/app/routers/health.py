"""Health (liveness) and readiness endpoints.

``/health`` is a cheap **liveness** probe: it returns 200 as long as the process
is serving, and is safe for frequent polling. ``/readyz`` is the **readiness**
probe: it verifies the database pool is live (``SELECT 1``) and returns
``503`` + ``status="degraded"`` when the DB-backed routes (ingestion, retrieval,
RAG) cannot be served, so an orchestrator never routes dependent traffic to a
broken instance. Liveness stays green during a DB outage *on purpose* —
restarting the process will not fix an external database, so only readiness
should flip.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from app import __version__
from app.fixtures import FIXTURE_DOCUMENTS
from app.models import DocumentSummary, HealthStatus

logger = logging.getLogger("veridoc.ai")

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
async def health(request: Request) -> HealthStatus:
    """Liveness: the process is up and serving. Does not touch the database."""
    settings = request.app.state.settings
    return HealthStatus(
        status="ok",
        service="veridoc-ai",
        version=__version__,
        mock=settings.is_mock,
    )


@router.get("/readyz", response_model=HealthStatus)
async def readyz(request: Request, response: Response) -> HealthStatus:
    """Readiness: the DB-backed routes can actually be served.

    Returns 503 + ``degraded`` when the pool is missing or a ``SELECT 1`` fails,
    so Compose/k8s mark the instance not-ready instead of shipping a DB outage as
    green. The check never raises — a failed probe is a 503, not a 500.
    """
    settings = request.app.state.settings
    pool = getattr(request.app.state, "pool", None)
    db_ok = False
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception as exc:  # noqa: BLE001 - readiness must never raise
            logger.warning("readiness: database check failed (%s)", exc)

    if not db_ok:
        response.status_code = 503
    return HealthStatus(
        status="ok" if db_ok else "degraded",
        service="veridoc-ai",
        version=__version__,
        mock=settings.is_mock,
    )


@router.get("/v1/documents", response_model=list[DocumentSummary])
async def list_documents() -> list[DocumentSummary]:
    """Return the synthetic fixture documents available for Q&A."""
    return FIXTURE_DOCUMENTS
