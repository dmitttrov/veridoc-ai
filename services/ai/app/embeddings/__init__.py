"""Pluggable embedding providers (deterministic + real local model)."""
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import build_embedding_provider

__all__ = ["EmbeddingProvider", "build_embedding_provider"]
