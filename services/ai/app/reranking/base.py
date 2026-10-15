"""Reranker abstraction.

A reranker scores (query, passage) pairs directly, which is more accurate than
the first-stage bag-of-words / vector retrieval but too expensive to run over
the whole corpus — hence the two-stage design: cheap retrieval narrows to a
candidate set, the reranker reorders it.

Reranker scores are on their OWN scale and are NOT comparable to RRF `fused`
scores. The pipeline keeps them in separate fields.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Reranker(Protocol):
    @property
    def model_id(self) -> str: ...

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Return one relevance score per passage, aligned to input order.
        Higher is more relevant."""
        ...
