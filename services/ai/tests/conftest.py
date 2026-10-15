"""Shared fixtures. DB-dependent tests are gated on VERIDOC_TEST_DATABASE_URL
and skipped (not failed) when no test database is configured."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app.config import Settings
from app.db.migrate import run_migrations
from app.db.pool import create_pool
from app.embeddings import build_embedding_provider

TEST_DB_ENV = "VERIDOC_TEST_DATABASE_URL"


def _db_url() -> str | None:
    return os.environ.get(TEST_DB_ENV)


requires_db = pytest.mark.skipif(
    _db_url() is None,
    reason=f"set {TEST_DB_ENV} to run database integration tests",
)


@pytest.fixture
def settings() -> Settings:
    url = _db_url() or "postgresql://veridoc:veridoc@localhost:5433/veridoc"
    return Settings(
        database_url=url,
        embedding_provider="deterministic",
        embedding_dim=384,
    )


@pytest.fixture
def embedder(settings: Settings):
    return build_embedding_provider(settings)


@pytest_asyncio.fixture
async def pool(settings: Settings) -> AsyncIterator[object]:
    await run_migrations(settings.database_url)
    pool = await create_pool(settings)
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE document_chunks, document_pages, ingestion_runs, documents "
            "RESTART IDENTITY CASCADE"
        )
    try:
        yield pool
    finally:
        await pool.close()
