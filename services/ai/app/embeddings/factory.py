"""Select and construct the configured embedding provider."""
from __future__ import annotations

from app.config import Settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.deterministic import DeterministicEmbeddingProvider

# The DB embedding column is fixed at vector(384) with CHECK (embedding_dim = 384)
# in app/db/migrations/0001_init.sql. Changing the dimension requires a new
# migration, so reject a mismatched AI_EMBEDDING_DIM at startup rather than
# failing deep inside the first insert.
SUPPORTED_EMBEDDING_DIM = 384


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_dim != SUPPORTED_EMBEDDING_DIM:
        raise ValueError(
            f"AI_EMBEDDING_DIM={settings.embedding_dim} is unsupported; the database "
            f"schema fixes the embedding column at vector({SUPPORTED_EMBEDDING_DIM}). "
            "Changing the dimension requires a new migration."
        )

    provider: EmbeddingProvider
    if settings.embedding_provider == "deterministic":
        provider = DeterministicEmbeddingProvider(dim=settings.embedding_dim)
    elif settings.embedding_provider == "sentence-transformers":
        from app.embeddings.sentence_transformers import (
            SentenceTransformersEmbeddingProvider,
        )

        provider = SentenceTransformersEmbeddingProvider(
            model_name=settings.sentence_transformers_model,
            expected_dim=settings.embedding_dim,
        )
    else:
        raise ValueError(
            f"Unknown AI_EMBEDDING_PROVIDER={settings.embedding_provider!r}. "
            "Supported: 'deterministic', 'sentence-transformers'."
        )

    # Enforce the schema's fixed dimension; never silently mix dimensions.
    if provider.dim != settings.embedding_dim:
        raise ValueError(
            f"Embedding provider dim {provider.dim} != configured "
            f"embedding_dim {settings.embedding_dim}."
        )
    return provider
