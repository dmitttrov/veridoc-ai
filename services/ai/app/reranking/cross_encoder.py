"""Real local cross-encoder reranker (sentence-transformers CrossEncoder).

Default model: cross-encoder/ms-marco-MiniLM-L-6-v2 (Apache-2.0, CPU-friendly).
Heavy dependencies (torch, sentence-transformers) are the optional [embeddings]
extra and are imported lazily — nothing loads unless this reranker is selected.
"""
from __future__ import annotations

from typing import Any


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder  # lazy, optional dep

        self._model_name = model_name
        self._model: Any = CrossEncoder(model_name)

    @property
    def model_id(self) -> str:
        return self._model_name

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        pairs = [[query, p] for p in passages]
        scores = self._model.predict(pairs)
        return [float(s) for s in scores]
