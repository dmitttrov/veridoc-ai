"""Health and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.fixtures import FIXTURE_DOCUMENTS
from app.models import DocumentSummary, HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
async def health(request: Request) -> HealthStatus:
    settings = request.app.state.settings
    return HealthStatus(
        status="ok",
        service="veridoc-ai",
        version=__version__,
        mock=settings.is_mock,
    )


@router.get("/v1/documents", response_model=list[DocumentSummary])
async def list_documents() -> list[DocumentSummary]:
    """Return the synthetic fixture documents available for Q&A."""
    return FIXTURE_DOCUMENTS
