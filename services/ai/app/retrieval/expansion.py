"""Deterministic metric-synonym query expansion.

The measured authentic filing-text eval (docs/EVALUATION.md, 2026-11-05) found
retrieval vocabulary to be the binding constraint: users ask for "total
revenue" while filings print "Total net sales", and only 42% of questions got
a gold-bearing passage into the top-5 even with semantic embeddings and a
cross-encoder. This module closes that gap the Veridoc way — a curated,
deterministic financial-metric synonym lexicon, no LLM call, no network, fully
reproducible (ADR-0028).

`expand_query` returns the original query first, then variants with the single
longest recognized metric phrase substituted by its filing-vocabulary
synonyms. The retrieval service runs every variant through both legs and
fuses all rankings with the existing RRF, so expansion can only add candidate
rankings — the original query's rankings are always present.
"""
from __future__ import annotations

import re

# Curated synonym groups: question-style phrasing first, then phrasings as
# printed in real 10-K statements. Groups are intentionally high-precision —
# a wrong synonym silently poisons retrieval, so when in doubt, leave it out.
# Singleton phrases ("total assets") have no useful aliases and are omitted.
_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "total revenue",
        "total net sales",
        "net sales",
        "total revenues",
        "net revenue",
        "revenues",
    ),
    (
        "operating income",
        "income from operations",
        "operating profit",
    ),
    (
        "net income",
        "net earnings",
        "net income (loss)",
    ),
    (
        "net cash from operating activities",
        "net cash provided by operating activities",
        "cash provided by operating activities",
        "net cash provided by (used in) operating activities",
        "operating cash flow",
    ),
    (
        "stockholders equity",
        "stockholders' equity",
        "shareholders' equity",
        "shareholders equity",
        "total stockholders' equity",
        "total equity",
    ),
    (
        "cash and cash equivalents",
        "cash and equivalents",
    ),
)

# Longest phrases first so "net cash from operating activities" wins over
# "net income"-style shorter matches inside the same query.
_PHRASES: list[tuple[str, tuple[str, ...]]] = sorted(
    ((phrase, group) for group in _GROUPS for phrase in group),
    key=lambda item: -len(item[0]),
)

DEFAULT_MAX_VARIANTS = 4


def expand_query(query: str, max_variants: int = DEFAULT_MAX_VARIANTS) -> list[str]:
    """Return [query, *synonym variants], deduplicated, capped, deterministic.

    Only the single longest recognized phrase is substituted — multi-phrase
    queries would multiply variants combinatorially for little retrieval gain.
    A query with no recognized metric phrase returns just [query].
    """
    lowered = query.lower()
    for phrase, group in _PHRASES:
        match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered)
        if not match:
            continue
        start, end = match.span()
        variants = [query]
        for synonym in group:
            if synonym == phrase:
                continue
            candidate = query[:start] + synonym + query[end:]
            if candidate not in variants:
                variants.append(candidate)
            if len(variants) >= max_variants:
                break
        return variants
    return [query]
