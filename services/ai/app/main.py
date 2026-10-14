"""FastAPI application entrypoint for the Veridoc AI inference service.

This service is INTERNAL ONLY. It must not be exposed to the public internet;
the NestJS gateway is the sole client, reaching it over the private network.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.config import get_settings
from app.db.pool import create_pool
from app.embeddings import build_embedding_provider
from app.logging_config import (
    REQUEST_ID_HEADER,
    configure_logging,
    new_request_id,
    request_id_var,
    sanitize_request_id,
)
from app.providers import build_provider
from app.reranking import build_reranker
from app.routers import chat, documents, health, rag, retrieve

configure_logging()

logger = logging.getLogger("veridoc.ai")


class RequestIdMiddleware:
    """Pure-ASGI correlation-id middleware.

    Binds ``x-request-id`` (reused from the gateway or freshly minted) to a
    context variable for the whole request — including SSE body generation — and
    echoes it on the response. Implemented at the ASGI layer (not
    ``BaseHTTPMiddleware``) so it never buffers streaming responses.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers: dict[bytes, bytes] = dict(scope.get("headers") or [])
        incoming = headers.get(REQUEST_ID_HEADER.encode())
        request_id = (
            sanitize_request_id(incoming.decode("latin-1") if incoming else None)
            or new_request_id()
        )
        token = request_id_var.set(request_id)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw = list(message.get("headers") or [])
                raw.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": raw}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    app.state.embedder = build_embedding_provider(settings)
    app.state.reranker = build_reranker(settings)
    # Bounds how many uploads are parsed/embedded at once (memory + CPU).
    app.state.ingest_semaphore = asyncio.Semaphore(settings.max_concurrent_ingestions)

    # The DB is required for ingestion/retrieval but NOT for the Phase 1 chat
    # mock path. Degrade gracefully if it is unavailable so the mock keeps
    # working; ingestion/retrieval endpoints then return 503.
    app.state.pool = None
    try:
        app.state.pool = await create_pool(settings)
        logger.info("database pool ready")
    except Exception as exc:  # noqa: BLE001 - startup must not hard-fail
        logger.warning("database unavailable; ingestion/retrieval disabled (%s)", exc)

    reranker = app.state.reranker
    logger.info(
        "AI service starting (inference=%s, mock=%s, embedder=%s dim=%d, reranker=%s)",
        settings.inference_provider,
        settings.is_mock,
        app.state.embedder.model_id,
        app.state.embedder.dim,
        reranker.model_id if reranker else "none",
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

    # Outermost middleware: tag every request/log with a correlation id.
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router, tags=["health"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(retrieve.router, tags=["retrieval"])
    app.include_router(rag.router, tags=["rag"])
    return app


app = create_app()
