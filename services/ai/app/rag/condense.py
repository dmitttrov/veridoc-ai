"""Deterministic condensation of a conversation into a standalone retrieval query.

A follow-up question ("what about 2022?") usually lacks the terms retrieval
needs. Many RAG systems rewrite it with an extra LLM call; that doubles
latency, adds a failure mode, and is non-reproducible. Veridoc instead builds
the retrieval query deterministically: the current question plus the most
recent prior *user* turns, bounded to the retrieval contract's query limit
(ADR-0026). Hybrid lexical+vector retrieval tolerates the extra terms well,
and the generation prompt separately receives the bounded conversation so the
model resolves pronouns at answer time.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.models import ChatMessage

# Hard bound from the retrieval contract (RetrievalRequest.query max_length).
MAX_QUERY_CHARS = 2000
# How many recent prior user turns are folded into the retrieval query. More
# turns add recall for long chains of follow-ups but dilute the lexical leg.
_MAX_CONTEXT_TURNS = 4


def condense_query(question: str, history: Sequence[ChatMessage]) -> str:
    """Build a standalone retrieval query from the question and conversation.

    Deterministic and bounded: the current question always comes first (it
    dominates both retrieval legs), followed by up to ``_MAX_CONTEXT_TURNS``
    most-recent user turns, newest first, within ``MAX_QUERY_CHARS`` total.
    Assistant turns are excluded: they are model output, and folding them in
    would let a prior answer steer retrieval toward itself.
    """
    base = question.strip() or question  # contract guarantees >= 1 char
    parts = [base]
    used = len(base)
    taken = 0

    for message in reversed(history):
        if taken >= _MAX_CONTEXT_TURNS:
            break
        if message.role != "user":
            continue
        text = message.content.strip()
        if not text:
            continue
        if used + 1 + len(text) > MAX_QUERY_CHARS:
            break
        parts.append(text)
        used += 1 + len(text)
        taken += 1

    return "\n".join(parts)[:MAX_QUERY_CHARS]
