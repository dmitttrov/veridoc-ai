"""FastAPI application entrypoint for the Veridoc AI inference service.

This service is INTERNAL ONLY. It must not be exposed to the public internet;
the NestJS gateway is the sole client, reaching it over the private network.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db.pool import create_pool
from app.embeddings import build_embedding_provider
from app.providers import build_provider
from app.routers import chat, documents, health, retrieve

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("veridoc.ai")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    app.state.embedder = build_embedding_provider(settings)

    # The DB is required for ingestion/retrieval but NOT for the Phase 1 chat
    # mock path. Degrade gracefully if it is unavailable so the mock keeps
    # working; ingestion/retrieval endpoints then return 503.
    app.state.pool = None
    try:
        app.state.pool = await create_pool(settings)
        logger.info("database pool ready")
    except Exception as exc:  # noqa: BLE001 - startup must not hard-fail
        logger.warning("database unavailable; ingestion/retrieval disabled (%s)", exc)

    logger.info(
        "AI service starting (provider=%s, mock=%s, embedder=%s, dim=%d)",
        settings.provider,
        settings.is_mock,
        app.state.embedder.model_id,
        app.state.embedder.dim,
    )
    try:
        yield
    finally:
        if app.state.pool is not None:
            await app.state.pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Veridoc AI Service",
        version=__version__,
        description="Internal inference + retrieval service. Mock generation in Phase 1-2.",
        lifespan=lifespan,
    )

    # The gateway talks to this service server-to-server, so CORS is normally
    # unnecessary. It is configurable but defaults to empty (no browser origins).
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    app.include_router(health.router, tags=["health"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(retrieve.router, tags=["retrieval"])
    return app


app = create_app()
