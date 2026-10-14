"""Grounded RAG orchestration + citation verification.

Citation verification here establishes *validity* — that each cited marker maps
to a passage that was actually retrieved and is traceable to a stored document
span. It deliberately does NOT attempt to verify that the cited evidence
semantically *supports* the claim; that is a separate, harder problem and we do
not represent validity as support.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import asyncpg

from app.config import Settings
from app.embeddings.base import EmbeddingProvider
from app.models import Citation, RetrievalRequest, RetrievedPassage
from app.providers.base import GenerationResult, InferenceProvider
from app.rag.prompt import ABSTAIN_SENTINEL, build_messages, marker_for
from app.reranking.base import Reranker
from app.retrieval.service import retrieve as run_retrieve

logger = logging.getLogger("veridoc.ai.rag")

_MARKER = re.compile(r"\[(E\d+)\]")
_SNIPPET_CHARS = 600


@dataclass
class RagOutcome:
    answer: str
    abstained: bool
    citations: list[Citation]
    invalid_citation_count: int
    passages: list[RetrievedPassage]
    model: str
    mock: bool
    reranked: bool = False
    reranker_model: str | None = None
    token_count: int = 0


def _snippet(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _SNIPPET_CHARS else text[:_SNIPPET_CHARS] + "…"


def verify_citations(
    answer_text: str, passages: list[RetrievedPassage]
) -> tuple[str, list[Citation], int]:
    """Validate the markers the model emitted.

    Returns (cleaned_answer, valid_citations, invalid_count). Markers that do
    not map to a retrieved passage are fabricated: they are stripped from the
    answer and counted, never surfaced as citations.
    """
    marker_to_passage = {marker_for(i): p for i, p in enumerate(passages)}

    emitted = _MARKER.findall(answer_text)
    valid_markers: list[str] = []
    invalid_count = 0
    seen_valid: set[str] = set()
    cleaned = answer_text

    for marker in emitted:
        if marker in marker_to_passage:
            if marker not in seen_valid:
                seen_valid.add(marker)
                valid_markers.append(marker)
        else:
            invalid_count += 1
            # Remove the fabricated marker token from the displayed answer.
            cleaned = cleaned.replace(f"[{marker}]", "")

    citations: list[Citation] = []
    for marker in valid_markers:
        p = marker_to_passage[marker]
        citations.append(
            Citation(
                document_id=p.document_id,
                document_title=p.document_title,
                page=p.page,
                snippet=_snippet(p.text),
                chunk_id=p.chunk_id,
                char_start=p.char_start,
                char_end=p.char_end,
                marker=marker,
            )
        )
    return re.sub(r"\s{2,}", " ", cleaned).strip(), citations, invalid_count


async def answer_question(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    reranker: Reranker | None,
    provider: InferenceProvider,
    settings: Settings,
    *,
    question: str,
    document_ids: list[str],
    top_k: int,
    rerank: bool | None,
) -> RagOutcome:
    retrieval = await run_retrieve(
        pool,
        embedder,
        RetrievalRequest(
            query=question, document_ids=document_ids, top_k=top_k, rerank=rerank
        ),
        reranker,
        rerank_candidate_k=settings.rerank_candidate_k,
    )
    passages = retrieval.passages

    # No evidence -> abstain without calling the model.
    if not passages:
        return RagOutcome(
            answer=(
                "I don't have enough evidence in the selected documents to answer "
                "that question."
            ),
            abstained=True,
            citations=[],
            invalid_citation_count=0,
            passages=[],
            model=provider.name,
            mock=provider.is_mock,
            reranked=retrieval.reranked,
            reranker_model=retrieval.reranker_model,
        )

    messages = build_messages(question, passages)
    result: GenerationResult = await provider.generate(
        messages,
        max_tokens=settings.inference_max_tokens,
        temperature=settings.inference_temperature,
    )

    raw = result.text.strip()
    # Defensive cap: bound memory + the token list if a provider ignores
    # max_tokens and returns a pathologically long answer.
    if len(raw) > settings.max_answer_chars:
        logger.warning(
            "rag answer truncated from %d to %d chars", len(raw), settings.max_answer_chars
        )
        raw = raw[: settings.max_answer_chars]
    if ABSTAIN_SENTINEL in raw:
        return RagOutcome(
            answer=(
                "I don't have enough evidence in the selected documents to answer "
                "that question."
            ),
            abstained=True,
            citations=[],
            invalid_citation_count=0,
            passages=passages,
            model=result.model,
            mock=provider.is_mock,
            reranked=retrieval.reranked,
            reranker_model=retrieval.reranker_model,
            token_count=result.token_count,
        )

    cleaned, citations, invalid_count = verify_citations(raw, passages)
    return RagOutcome(
        answer=cleaned,
        abstained=False,
        citations=citations,
        invalid_citation_count=invalid_count,
        passages=passages,
        model=result.model,
        mock=provider.is_mock,
        reranked=retrieval.reranked,
        reranker_model=retrieval.reranker_model,
        token_count=result.token_count,
    )
