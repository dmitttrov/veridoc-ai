"""Database-backed ingestion + retrieval integration tests.

Gated on VERIDOC_TEST_DATABASE_URL (a running PostgreSQL+pgvector). Run with:
    VERIDOC_TEST_DATABASE_URL=postgresql://veridoc:veridoc@localhost:5433/veridoc pytest
"""
from __future__ import annotations

import asyncpg
import pytest

from app.db import repository as repo
from app.eval.corpus import ACME, GLOBEX
from app.eval.pdf_build import build_pdf
from app.ingestion.pipeline import ingest_pdf
from app.models import RetrievalRequest
from app.retrieval.service import retrieve
from tests.conftest import requires_db

pytestmark = requires_db

ACME_PDF = build_pdf(ACME.pages)
GLOBEX_PDF = build_pdf(GLOBEX.pages)


async def _ingest(pool, embedder, settings, data, filename):
    return await ingest_pdf(
        pool, embedder, settings, data=data, filename=filename, mime_type="application/pdf"
    )


async def test_ingest_stores_document_pages_and_chunks(pool, embedder, settings) -> None:
    result = await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")
    assert result.state == "succeeded"
    assert result.already_ingested is False
    assert result.page_count == len(ACME.pages)
    assert result.chunk_count > 0

    async with pool.acquire() as conn:
        docs = await conn.fetchval("SELECT count(*) FROM documents")
        pages = await conn.fetchval("SELECT count(*) FROM document_pages")
        chunks = await conn.fetchval("SELECT count(*) FROM document_chunks")
    assert docs == 1
    assert pages == len(ACME.pages)
    assert chunks == result.chunk_count


async def test_reingestion_is_idempotent(pool, embedder, settings) -> None:
    first = await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")
    second = await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")

    assert second.already_ingested is True
    assert second.document_id == first.document_id
    assert second.chunk_count == first.chunk_count

    async with pool.acquire() as conn:
        docs = await conn.fetchval("SELECT count(*) FROM documents")
        chunks = await conn.fetchval("SELECT count(*) FROM document_chunks")
        runs = await conn.fetchval("SELECT count(*) FROM ingestion_runs")
    assert docs == 1  # no duplicate document
    assert chunks == first.chunk_count  # no duplicate chunks
    assert runs == 2  # both attempts recorded


async def test_transaction_rolls_back_on_store_failure(
    pool, embedder, settings, monkeypatch
) -> None:
    calls = {"n": 0}
    real_insert = repo.insert_chunk

    async def flaky_insert(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated storage failure")
        return await real_insert(*args, **kwargs)

    monkeypatch.setattr(repo, "insert_chunk", flaky_insert)

    with pytest.raises(RuntimeError):
        await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")

    async with pool.acquire() as conn:
        docs = await conn.fetchval("SELECT count(*) FROM documents")
        pages = await conn.fetchval("SELECT count(*) FROM document_pages")
        chunks = await conn.fetchval("SELECT count(*) FROM document_chunks")
        failed = await conn.fetchval(
            "SELECT count(*) FROM ingestion_runs WHERE state = 'failed'"
        )
    # Everything in the store transaction rolled back.
    assert docs == 0 and pages == 0 and chunks == 0
    # The failed attempt is recorded.
    assert failed == 1


async def test_keyword_retrieval_finds_expected_page(pool, embedder, settings) -> None:
    await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")
    resp = await retrieve(
        pool, embedder, RetrievalRequest(query="research and development expenses", top_k=5)
    )
    assert resp.passages
    top = resp.passages[0]
    assert top.page == 3  # the R&D page
    assert top.scores.lexical > 0


async def test_vector_leg_returns_results(pool, embedder, settings) -> None:
    await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")
    resp = await retrieve(
        pool, embedder, RetrievalRequest(query="cash and cash equivalents liquidity", top_k=5)
    )
    assert any(p.scores.semantic > 0 for p in resp.passages)
    assert any(p.page == 4 for p in resp.passages)


async def test_document_filter_restricts_results(pool, embedder, settings) -> None:
    acme = await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")
    await _ingest(pool, embedder, settings, GLOBEX_PDF, "globex.pdf")

    resp = await retrieve(
        pool,
        embedder,
        RetrievalRequest(query="revenue", document_ids=[acme.document_id], top_k=10),
    )
    assert resp.passages
    assert all(p.document_id == acme.document_id for p in resp.passages)


async def test_every_citation_is_traceable_to_page_text(pool, embedder, settings) -> None:
    import uuid as _uuid

    await _ingest(pool, embedder, settings, ACME_PDF, "acme.pdf")
    resp = await retrieve(
        pool, embedder, RetrievalRequest(query="segment revenue americas emea apac", top_k=10)
    )
    assert resp.passages
    async with pool.acquire() as conn:
        for p in resp.passages:
            page_text = await repo.get_page_text(
                conn, _uuid.UUID(p.document_id), p.page
            )
            assert page_text is not None
            # The returned evidence is EXACTLY the stored page slice.
            assert p.text == page_text[p.char_start : p.char_end]
            assert p.citation.endswith(f"p.{p.page}")


async def test_db_rejects_wrong_dimension_embedding(pool) -> None:
    # The embedding column is vector(384); a mismatched dimension is rejected by
    # PostgreSQL itself, so incompatible embeddings can never be stored/mixed.
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.PostgresError):
            await conn.fetchval("SELECT '[1,2,3]'::vector(384)")
