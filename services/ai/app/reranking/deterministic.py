"""Deterministic reranker for tests, CI, and reproducible evaluation.

Scores a passage by weighted lexical overlap with the query: the fraction of
distinct query terms present in the passage, with a small bonus for term
frequency. Fully deterministic, dependency-free, and — unlike the first-stage
RRF ordering — it is a genuine (query, passage) scoring function, so it
exercises the reranking code path end to end.

It is NOT a semantic model; it is a stand-in so reranking can be tested without
downloading weights.
"""
from __future__ import annotations

import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")

MODEL_ID = "veridoc-deterministic-reranker-v1"

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "of", "and", "or", "to", "in", "for", "on", "was",
        "were", "is", "are", "what", "how", "much", "did", "does", "do",
        "its", "it", "at", "by", "with", "as", "that", "this",
    }
)


def _terms(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


class DeterministicReranker:
    @property
    def model_id(self) -> str:
        return MODEL_ID

    def score(self, query: str, passages: list[str]) -> list[float]:
        query_terms = set(_terms(query))
        if not query_terms:
            return [0.0] * len(passages)

        scores: list[float] = []
        for passage in passages:
            passage_terms = _terms(passage)
            if not passage_terms:
                scores.append(0.0)
                continue
            counts = {t: passage_terms.count(t) for t in query_terms}
            matched = sum(1 for t in query_terms if counts[t] > 0)
            coverage = matched / len(query_terms)
            # Small sublinear term-frequency bonus, bounded so coverage dominates.
            tf_bonus = sum(math.log1p(counts[t]) for t in query_terms) / (
                10.0 * len(query_terms)
            )
            scores.append(round(coverage + tf_bonus, 6))
        return scores
