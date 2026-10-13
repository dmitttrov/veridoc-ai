"""Inference providers.

The `InferenceProvider` protocol is the seam that lets Phase 1 run entirely on
a deterministic mock while later phases plug in an OpenAI-compatible client
(e.g. a local vLLM server) without touching the API surface.
"""
from __future__ import annotations

from app.config import Settings
from app.providers.base import (
    ChatMessage,
    GenerationResult,
    InferenceError,
    InferenceProvider,
)
from app.providers.mock import MockProvider


def build_provider(settings: Settings) -> InferenceProvider:
    """Factory selecting a provider from configuration.

    Never silently substitutes the mock for a misconfigured real provider — a
    bad configuration raises loudly here, at startup.
    """
    if settings.inference_provider == "mock":
        return MockProvider(
            model_name=settings.model_name,
            token_delay_s=settings.stream_token_delay_s,
        )
    if settings.inference_provider == "openai_compatible":
        from app.providers.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            base_url=settings.inference_base_url,
            model=settings.inference_model,
            api_key=settings.inference_api_key,
            timeout_s=settings.inference_timeout_s,
        )
    raise ValueError(
        f"Unknown AI_INFERENCE_PROVIDER={settings.inference_provider!r}. "
        "Supported: 'mock', 'openai_compatible'."
    )


__all__ = [
    "ChatMessage",
    "GenerationResult",
    "InferenceError",
    "InferenceProvider",
    "MockProvider",
    "build_provider",
]
