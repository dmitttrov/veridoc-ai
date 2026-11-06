"""Hybrid retrieval service.

Combines two independent retrieval legs over ``document_chunks``:
  * lexical  — PostgreSQL full-text search (``websearch_to_tsquery`` + ``ts_rank_cd``)
  * semantic — pgvector cosine similarity against the query embedding

and fuses them with Reciprocal Rank Fusion (RRF). Only chunks embedded by the
active model are considered, so embeddings from different models/dimensions are
never compared.

Every returned passage's ``text`` is the stored chunk text, which by
construction equals ``document_pages.normalized_text[char_start:char_end]`` for
its page — so each citation is traceable to stored page text.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import asyncpg

from app.embeddings.base import EmbeddingProvider
from app.models import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalScores,
    RetrievedPassage,
)
from app.reranking.base import Reranker
from app.retrieval.expansion import expand_query

# RRF constant. 60 is the value from the original Cormack et al. paper and is a
# robust default; larger values flatten the contribution of top ranks.
RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = RRF_K
) -> dict[str, float]:
    """Pure Reciprocal Rank Fusion. Each list is item ids in descending rank.

    Returns item id -> fused score (sum of 1/(k + rank) across lists where the
    item appears, rank being 0-based). Pure and deterministic — unit-tested.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return scores


@dataclass
class _Candidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: int
    char_start: int
    char_end: int
    text: str
    lexical: float = 0.0
    semantic: float = 0.0
    fused: float = 0.0
    rerank: float | None = None


_LEXICAL_SQL = """
    SELECT c.id, c.document_id, d.title AS document_title, c.page_number,
           c.char_start, c.char_end, c.text,
           ts_rank_cd(c.text_tsv, q) AS score
    FROM document_chunks c
    JOIN documents d ON d.id = c.document_id,
         websearch_to_tsquery('english', $1) q
    WHERE c.text_tsv @@ q
      AND c.embedding_model = $2
      AND ($3::uuid[] IS NULL OR c.document_id = ANY($3))
    ORDER BY score DESC, c.id
    LIMIT $4
"""

_SEMANTIC_SQL = """
    SELECT c.id, c.document_id, d.title AS document_title, c.page_number,
           c.char_start, c.char_end, c.text,
           1 - (c.embedding <=> $1) AS score
    FROM document_chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.embedding_model = $2
      AND ($3::uuid[] IS NULL OR c.document_id = ANY($3))
    ORDER BY c.embedding <=> $1, c.id
    LIMIT $4
"""


def _to_uuid_list(ids: list[str]) -> list[uuid.UUID] | None:
    return [uuid.UUID(x) for x in ids] if ids else None


def _candidate_from_row(row: asyncpg.Record) -> _Candidate:
    return _Candidate(
        chunk_id=row["id"],
        document_id=row["document_id"],
        document_title=row["document_title"],
        page_number=row["page_number"],
        char_start=row["char_start"],
        char_end=row["char_end"],
        text=row["text"],
    )


async def retrieve(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    request: RetrievalRequest,
    reranker: Reranker | None = None,
    *,
    rerank_candidate_k: int = 20,
    expand_queries: bool = False,
) -> RetrievalResponse:
    # Decide whether reranking applies: a reranker must exist AND the request
    # must not have explicitly disabled it.
    apply_rerank = reranker is not None and request.rerank is not False
    # First stage must surface enough candidates for the reranker to reorder.
    first_stage_k = max(rerank_candidate_k, request.top_k) if apply_rerank else request.top_k
    candidate_pool = max(first_stage_k, request.top_k * 4, 20)

    doc_filter = _to_uuid_list(request.document_ids)
    # Metric-synonym expansion (deterministic, ADR-0028): each variant runs
    # both legs and contributes its own rankings to RRF. The original query's
    # rankings are always included, so expansion only ADDS evidence paths.
    variants = expand_query(request.query) if expand_queries else [request.query]
    variant_vecs = await asyncio.to_thread(embedder.embed, variants)

    lexical_lists: list[list[asyncpg.Record]] = []
    semantic_lists: list[list[asyncpg.Record]] = []
    async with pool.acquire() as conn:
        for variant, vec in zip(variants, variant_vecs, strict=True):
            lexical_lists.append(
                list(
                    await conn.fetch(
                        _LEXICAL_SQL, variant, embedder.model_id, doc_filter, candidate_pool
                    )
                )
            )
            semantic_lists.append(
                list(
                    await conn.fetch(
                        _SEMANTIC_SQL, vec, embedder.model_id, doc_filter, candidate_pool
                    )
                )
                if any(v != 0.0 for v in vec)
                else []
            )

    # Per-leg scores keep their meaning ("0 when not matched"): a candidate's
    # leg score is its best score for that leg across variants.
    candidates: dict[uuid.UUID, _Candidate] = {}
    for rows in lexical_lists:
        for row in rows:
            cand = candidates.setdefault(row["id"], _candidate_from_row(row))
            cand.lexical = max(cand.lexical, float(row["score"]))
    for rows in semantic_lists:
        for row in rows:
            cand = candidates.setdefault(row["id"], _candidate_from_row(row))
            cand.semantic = max(cand.semantic, float(row["score"]))

    fused = reciprocal_rank_fusion(
        [[str(r["id"]) for r in rows] for rows in (*lexical_lists, *semantic_lists)]
    )
    for cand in candidates.values():
        cand.fused = fused.get(str(cand.chunk_id), 0.0)

    # First stage: order by RRF and keep the candidate window.
    first_stage = sorted(
        candidates.values(), key=lambda c: (-c.fused, str(c.chunk_id))
    )[:first_stage_k]

    reranked = False
    reranker_model: str | None = None
    if apply_rerank and first_stage and reranker is not None:
        scores = await asyncio.to_thread(
            reranker.score, request.query, [c.text for c in first_stage]
        )
        for cand, score in zip(first_stage, scores, strict=True):
            cand.rerank = float(score)
        # Second stage: order by reranker score; RRF + id break ties stably.
        final = sorted(
            first_stage,
            key=lambda c: (-(c.rerank if c.rerank is not None else 0.0), -c.fused, str(c.chunk_id)),
        )[: request.top_k]
        reranked = True
        reranker_model = reranker.model_id
    else:
        final = first_stage[: request.top_k]

    passages = [
        RetrievedPassage(
            chunk_id=str(c.chunk_id),
            document_id=str(c.document_id),
            document_title=c.document_title,
            page=c.page_number,
            text=c.text,
            char_start=c.char_start,
            char_end=c.char_end,
            scores=RetrievalScores(
                lexical=round(c.lexical, 6),
                semantic=round(c.semantic, 6),
                fused=round(c.fused, 6),
                rerank=round(c.rerank, 6) if c.rerank is not None else None,
            ),
            citation=f"{c.document_title}, p.{c.page_number}",
        )
        for c in final
    ]

    return RetrievalResponse(
        query=request.query,
        passages=passages,
        embedding_model=embedder.model_id,
        embedding_dim=embedder.dim,
        reranked=reranked,
        reranker_model=reranker_model,
        # Self-documenting reports: the exact variants that were fused, or
        # null when expansion was off / found no metric phrase.
        expanded_queries=variants if len(variants) > 1 else None,
    )
