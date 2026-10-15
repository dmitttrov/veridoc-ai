"""Data-access functions (raw SQL over asyncpg).

Deliberately a thin, explicit SQL layer (no ORM) so transactions, upserts, and
idempotency are obvious and auditable. All write inserts use deterministic ids
with ``ON CONFLICT DO NOTHING`` so re-ingesting identical content is a no-op.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class DocumentRow:
    id: uuid.UUID
    content_hash: str
    filename: str
    title: str
    mime_type: str
    size_bytes: int
    page_count: int


async def get_document(conn: asyncpg.Connection, document_id: uuid.UUID) -> DocumentRow | None:
    row = await conn.fetchrow(
        """
        SELECT id, content_hash, filename, title, mime_type, size_bytes, page_count
        FROM documents WHERE id = $1
        """,
        document_id,
    )
    if row is None:
        return None
    return DocumentRow(**dict(row))


async def count_chunks(conn: asyncpg.Connection, document_id: uuid.UUID) -> int:
    value = await conn.fetchval(
        "SELECT count(*) FROM document_chunks WHERE document_id = $1", document_id
    )
    return int(value or 0)


async def insert_document(
    conn: asyncpg.Connection,
    *,
    document_id: uuid.UUID,
    content_hash: str,
    filename: str,
    title: str,
    mime_type: str,
    size_bytes: int,
    page_count: int,
) -> None:
    await conn.execute(
        """
        INSERT INTO documents
            (id, content_hash, filename, title, mime_type, size_bytes, page_count)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (id) DO NOTHING
        """,
        document_id,
        content_hash,
        filename,
        title,
        mime_type,
        size_bytes,
        page_count,
    )


async def insert_page(
    conn: asyncpg.Connection,
    *,
    page_id: uuid.UUID,
    document_id: uuid.UUID,
    page_number: int,
    normalized_text: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO document_pages
            (id, document_id, page_number, normalized_text, char_count)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO NOTHING
        """,
        page_id,
        document_id,
        page_number,
        normalized_text,
        len(normalized_text),
    )


async def insert_chunk(
    conn: asyncpg.Connection,
    *,
    chunk_id: uuid.UUID,
    document_id: uuid.UUID,
    page_id: uuid.UUID,
    page_number: int,
    chunk_index: int,
    char_start: int,
    char_end: int,
    text: str,
    embedding: list[float],
    embedding_model: str,
    embedding_dim: int,
) -> None:
    await conn.execute(
        """
        INSERT INTO document_chunks
            (id, document_id, page_id, page_number, chunk_index,
             char_start, char_end, text, embedding, embedding_model, embedding_dim)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (id) DO NOTHING
        """,
        chunk_id,
        document_id,
        page_id,
        page_number,
        chunk_index,
        char_start,
        char_end,
        text,
        embedding,
        embedding_model,
        embedding_dim,
    )


async def create_run(
    conn: asyncpg.Connection,
    *,
    run_id: uuid.UUID,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content_hash: str | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO ingestion_runs
            (id, filename, mime_type, size_bytes, content_hash, state)
        VALUES ($1, $2, $3, $4, $5, 'running')
        """,
        run_id,
        filename,
        mime_type,
        size_bytes,
        content_hash,
    )


async def finish_run(
    conn: asyncpg.Connection,
    *,
    run_id: uuid.UUID,
    document_id: uuid.UUID | None,
    state: str,
    already_ingested: bool,
    page_count: int | None,
    chunk_count: int | None,
    error: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE ingestion_runs
        SET document_id = $2, state = $3::ingestion_state, already_ingested = $4,
            page_count = $5, chunk_count = $6, error = $7, finished_at = now()
        WHERE id = $1
        """,
        run_id,
        document_id,
        state,
        already_ingested,
        page_count,
        chunk_count,
        error,
    )


async def list_documents(conn: asyncpg.Connection) -> list[DocumentRow]:
    rows = await conn.fetch(
        """
        SELECT id, content_hash, filename, title, mime_type, size_bytes, page_count
        FROM documents ORDER BY created_at DESC
        """
    )
    return [DocumentRow(**dict(r)) for r in rows]


@dataclass(frozen=True)
class StoredDocumentRow:
    id: uuid.UUID
    title: str
    filename: str
    page_count: int
    size_bytes: int
    chunk_count: int


async def list_stored_documents(conn: asyncpg.Connection) -> list[StoredDocumentRow]:
    rows = await conn.fetch(
        """
        SELECT d.id, d.title, d.filename, d.page_count, d.size_bytes,
               count(c.id) AS chunk_count
        FROM documents d
        LEFT JOIN document_chunks c ON c.document_id = d.id
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """
    )
    return [StoredDocumentRow(**dict(r)) for r in rows]


async def get_page_text(
    conn: asyncpg.Connection, document_id: uuid.UUID, page_number: int
) -> str | None:
    value = await conn.fetchval(
        "SELECT normalized_text FROM document_pages WHERE document_id = $1 AND page_number = $2",
        document_id,
        page_number,
    )
    return value if value is None else str(value)
