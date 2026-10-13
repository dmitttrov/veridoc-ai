"""Embedding provider abstraction."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Produces fixed-dimensionality embeddings for text.

    Every provider reports a stable ``model_id`` and ``dim`` which are recorded
    alongside each stored vector so embeddings from different models/dimensions
    are never silently mixed at retrieval time.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector (length ``dim``) each."""
        ...
