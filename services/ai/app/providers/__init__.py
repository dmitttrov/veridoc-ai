"""Inference providers.

The `InferenceProvider` protocol is the seam that lets Phase 1 run entirely on
a deterministic mock while later phases plug in an OpenAI-compatible client
(e.g. a local vLLM server) without touching the API surface.
"""
from __future__ import annotations

from app.config import Settings
from app.providers.base import InferenceProvider
from app.providers.mock import MockProvider


def build_provider(settings: Settings) -> InferenceProvider:
    """Factory selecting a provider from configuration."""
    if settings.provider == "mock":
        return MockProvider(
            model_name=settings.model_name,
            token_delay_s=settings.stream_token_delay_s,
        )
    raise ValueError(
        f"Unknown AI_PROVIDER={settings.provider!r}. Phase 1 supports 'mock' only."
    )


__all__ = ["InferenceProvider", "MockProvider", "build_provider"]
