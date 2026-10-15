"""Real local embedding provider backed by sentence-transformers.

Uses `sentence-transformers/all-MiniLM-L6-v2` by default (Apache-2.0 licensed,
384-dim, small, CPU-friendly). The heavy dependencies (torch,
sentence-transformers) are an optional extra: `pip install -e ".[embeddings]"`.
Nothing here runs unless this provider is explicitly selected.
"""
from __future__ import annotations

from typing import Any


class SentenceTransformersEmbeddingProvider:
    def __init__(self, model_name: str, expected_dim: int) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only when selected
            raise RuntimeError(
                "sentence-transformers is not installed. Install the optional "
                'extra: pip install -e ".[embeddings]"'
            ) from exc

        self._model_name = model_name
        self._model: Any = SentenceTransformer(model_name)
        reported = self._model.get_sentence_embedding_dimension()
        if reported is None:
            raise RuntimeError(f"Model '{model_name}' did not report an embedding dimension.")
        dim = int(reported)
        if dim != expected_dim:
            raise ValueError(
                f"Model '{model_name}' produces {dim}-dim embeddings but the "
                f"configured/schema dimension is {expected_dim}. Refusing to "
                "mix incompatible dimensions."
            )
        self._dim = dim

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        # normalize_embeddings=True => unit vectors, so inner product == cosine.
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [[float(x) for x in row] for row in vectors]
