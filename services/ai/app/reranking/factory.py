"""Select and construct the configured reranker.

Returns ``None`` when reranking is disabled OR when a real reranker is
configured but cannot be loaded (missing optional dependency / model). This is
an EXPLICIT fallback: callers observe ``None`` and record ``reranked=False`` in
responses — the system never silently pretends reranking happened.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.reranking.base import Reranker
from app.reranking.deterministic import DeterministicReranker

logger = logging.getLogger("veridoc.ai.reranking")


def build_reranker(settings: Settings) -> Reranker | None:
    provider = settings.reranker_provider
    if provider == "none":
        return None
    if provider == "deterministic":
        return DeterministicReranker()
    if provider == "cross-encoder":
        try:
            from app.reranking.cross_encoder import CrossEncoderReranker

            return CrossEncoderReranker(settings.cross_encoder_model)
        except Exception as exc:  # noqa: BLE001 - explicit, logged fallback
            logger.warning(
                "cross-encoder reranker unavailable (%s); falling back to no reranking",
                exc,
            )
            return None
    raise ValueError(
        f"Unknown AI_RERANKER_PROVIDER={provider!r}. "
        "Supported: 'none', 'deterministic', 'cross-encoder'."
    )
