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
from app.providers import build_provider
from app.routers import chat, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    logging.getLogger("veridoc.ai").info(
        "AI service starting (provider=%s, mock=%s, model=%s)",
        settings.provider,
        settings.is_mock,
        settings.model_name,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Veridoc AI Service",
        version=__version__,
        description="Internal inference service. Deterministic mock provider in Phase 1.",
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
    return app


app = create_app()
