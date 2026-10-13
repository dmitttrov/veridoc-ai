"""Document ingestion + stored-document listing (Phase 2)."""
from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.db import repository as repo
from app.ingestion.errors import IngestionError, PdfTooLarge, UnsupportedMediaType
from app.ingestion.pipeline import ingest_pdf
from app.models import DocumentIngestionResult, StoredDocument

logger = logging.getLogger("veridoc.ai.documents")

router = APIRouter()

_ALLOWED_MIME_TYPES = ("application/pdf",)


def _require_pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Database is not available."},
        )
    return pool


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, rejecting once the size limit is exceeded
    (avoids buffering an unbounded body before checking its size)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PdfTooLarge(f"Upload exceeds the {max_bytes}-byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/v1/documents/ingest", response_model=DocumentIngestionResult)
async def ingest(request: Request, file: UploadFile = File(...)) -> DocumentIngestionResult:
    settings = request.app.state.settings
    pool = _require_pool(request)

    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in _ALLOWED_MIME_TYPES:
        raise _ingestion_http(
            UnsupportedMediaType(f"Unsupported content type: {content_type or 'unknown'}")
        )

    try:
        data = await _read_limited(file, settings.max_upload_bytes)
        return await ingest_pdf(
            pool,
            request.app.state.embedder,
            settings,
            data=data,
            filename=file.filename or "upload.pdf",
            mime_type=content_type or "application/pdf",
        )
    except IngestionError as exc:
        raise _ingestion_http(exc) from exc


@router.get("/v1/documents/stored", response_model=list[StoredDocument])
async def stored(request: Request) -> list[StoredDocument]:
    pool = _require_pool(request)
    async with pool.acquire() as conn:
        rows = await repo.list_stored_documents(conn)
    return [
        StoredDocument(
            id=str(r.id),
            title=r.title,
            filename=r.filename,
            page_count=r.page_count,
            chunk_count=r.chunk_count,
            size_bytes=r.size_bytes,
        )
        for r in rows
    ]


def _ingestion_http(exc: IngestionError) -> HTTPException:
    return HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.message},
    )
