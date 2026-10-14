"""Ingestion orchestration: validate -> extract -> normalize -> chunk ->
embed -> store (transactionally, idempotently).

Idempotency: document, page, and chunk ids are deterministic UUIDv5 values
derived from the document's SHA-256 content hash, so re-ingesting identical
bytes maps to identical rows and the inserts no-op (ON CONFLICT DO NOTHING).
The whole store step runs in a single transaction: a failure rolls back every
row and the ingestion run is recorded as `failed`.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from pathlib import PurePath

import asyncpg

from app.config import Settings
from app.db import repository as repo
from app.embeddings.base import EmbeddingProvider
from app.ingestion.chunk import chunk_page_text
from app.ingestion.errors import IngestionError, PdfProcessingTimeout
from app.ingestion.normalize import normalize_text
from app.ingestion.pdf import validate_and_extract
from app.models import DocumentIngestionResult

logger = logging.getLogger("veridoc.ai.ingestion")

# Fixed namespace so deterministic ids are stable forever.
_NAMESPACE = uuid.UUID("7f5c1d2a-9e4b-5a6c-8d3e-2f1a0b9c8d7e")


def _document_id(content_hash: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"doc:{content_hash}")


def _page_id(content_hash: str, page_number: int) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"page:{content_hash}:{page_number}")


def chunk_id(content_hash: str, page_number: int, char_start: int, char_end: int) -> uuid.UUID:
    """Stable, reproducible chunk identity."""
    return uuid.uuid5(
        _NAMESPACE, f"chunk:{content_hash}:{page_number}:{char_start}:{char_end}"
    )


def _derive_title(filename: str) -> str:
    stem = PurePath(filename).stem.strip()
    pretty = stem.replace("_", " ").replace("-", " ").strip()
    return pretty or filename


async def ingest_pdf(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    settings: Settings,
    *,
    data: bytes,
    filename: str,
    mime_type: str,
) -> DocumentIngestionResult:
    content_hash = hashlib.sha256(data).hexdigest()
    document_id = _document_id(content_hash)
    title = _derive_title(filename)
    run_id = uuid.uuid4()

    # Record the attempt (committed immediately, outside the store transaction).
    async with pool.acquire() as conn:
        await repo.create_run(
            conn,
            run_id=run_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            content_hash=content_hash,
        )
        existing = await repo.get_document(conn, document_id)
        if existing is not None:
            chunk_count = await repo.count_chunks(conn, document_id)
            await repo.finish_run(
                conn,
                run_id=run_id,
                document_id=document_id,
                state="succeeded",
                already_ingested=True,
                page_count=existing.page_count,
                chunk_count=chunk_count,
                error=None,
            )
            logger.info("idempotent hit document=%s hash=%s", document_id, content_hash[:12])
            return DocumentIngestionResult(
                document_id=str(document_id),
                filename=existing.filename,
                content_hash=content_hash,
                mime_type=existing.mime_type,
                size_bytes=existing.size_bytes,
                page_count=existing.page_count,
                chunk_count=chunk_count,
                state="succeeded",
                already_ingested=True,
            )

    try:
        # Validation + extraction is CPU-bound; bound it with a wall-clock timeout.
        try:
            extracted = await asyncio.wait_for(
                asyncio.to_thread(
                    validate_and_extract,
                    data,
                    max_bytes=settings.max_upload_bytes,
                    max_pages=settings.max_pages,
                ),
                timeout=settings.pdf_parse_timeout_s,
            )
        except TimeoutError as exc:
            raise PdfProcessingTimeout("PDF processing exceeded the time limit.") from exc

        normalized_pages = [normalize_text(t) for t in extracted.page_texts]

        pending_chunks: list[tuple[int, uuid.UUID, int, int, int, str]] = []
        chunk_texts: list[str] = []
        for page_number, page_text in enumerate(normalized_pages, start=1):
            page_id = _page_id(content_hash, page_number)
            for ch in chunk_page_text(
                page_text,
                size=settings.chunk_size_chars,
                overlap=settings.chunk_overlap_chars,
            ):
                pending_chunks.append(
                    (page_number, page_id, ch.index, ch.char_start, ch.char_end, ch.text)
                )
                chunk_texts.append(ch.text)

        vectors = (
            await asyncio.to_thread(embedder.embed, chunk_texts) if chunk_texts else []
        )

        async with pool.acquire() as conn:
            try:
                async with conn.transaction():
                    await repo.insert_document(
                        conn,
                        document_id=document_id,
                        content_hash=content_hash,
                        filename=filename,
                        title=title,
                        mime_type=mime_type,
                        size_bytes=len(data),
                        page_count=extracted.page_count,
                    )
                    for page_number, page_text in enumerate(normalized_pages, start=1):
                        await repo.insert_page(
                            conn,
                            page_id=_page_id(content_hash, page_number),
                            document_id=document_id,
                            page_number=page_number,
                            normalized_text=page_text,
                        )
                    for (page_number, page_id, idx, start, end, text), vec in zip(
                        pending_chunks, vectors, strict=True
                    ):
                        await repo.insert_chunk(
                            conn,
                            chunk_id=chunk_id(content_hash, page_number, start, end),
                            document_id=document_id,
                            page_id=page_id,
                            page_number=page_number,
                            chunk_index=idx,
                            char_start=start,
                            char_end=end,
                            text=text,
                            embedding=vec,
                            embedding_model=embedder.model_id,
                            embedding_dim=embedder.dim,
                        )
            except Exception:
                # Transaction already rolled back; record the failed run.
                await repo.finish_run(
                    conn,
                    run_id=run_id,
                    document_id=None,
                    state="failed",
                    already_ingested=False,
                    page_count=None,
                    chunk_count=None,
                    error="storage_failed",
                )
                raise

            await repo.finish_run(
                conn,
                run_id=run_id,
                document_id=document_id,
                state="succeeded",
                already_ingested=False,
                page_count=extracted.page_count,
                chunk_count=len(pending_chunks),
                error=None,
            )

        logger.info(
            "ingested document=%s pages=%d chunks=%d model=%s",
            document_id,
            extracted.page_count,
            len(pending_chunks),
            embedder.model_id,
        )
        return DocumentIngestionResult(
            document_id=str(document_id),
            filename=filename,
            content_hash=content_hash,
            mime_type=mime_type,
            size_bytes=len(data),
            page_count=extracted.page_count,
            chunk_count=len(pending_chunks),
            state="succeeded",
            already_ingested=False,
        )

    except IngestionError as exc:
        # Expected rejection (bad/encrypted/oversized PDF, timeout). Record and
        # propagate; never log document content.
        async with pool.acquire() as conn:
            await repo.finish_run(
                conn,
                run_id=run_id,
                document_id=None,
                state="failed",
                already_ingested=False,
                page_count=None,
                chunk_count=None,
                error=exc.code,
            )
        logger.info("ingestion rejected code=%s file=%s", exc.code, filename)
        raise
