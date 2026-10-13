"""Reproducible retrieval evaluation.

Ingests the synthetic corpus into the configured database, runs hybrid
retrieval for each evaluation question, and reports **measured** Recall@5 and
MRR@10 over the known gold (document, page) citations. A result counts as
relevant when a returned passage's (document_id, page) matches the gold pair —
i.e. retrieval surfaced the correct page-level evidence.

Usage:
    python -m app.eval.run                 # human-readable report
    python -m app.eval.run --json          # machine-readable JSON

Requires a running PostgreSQL+pgvector and the dev extras installed. The
embedding provider is whatever is configured (AI_EMBEDDING_PROVIDER); the model
id is reported so results are never ambiguous or fabricated.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import asyncpg

from app.config import Settings, get_settings
from app.db.migrate import run_migrations
from app.db.pool import create_pool
from app.embeddings import build_embedding_provider
from app.embeddings.base import EmbeddingProvider
from app.eval.corpus import CORPUS, EVAL
from app.eval.pdf_build import build_pdf
from app.ingestion.pipeline import ingest_pdf
from app.models import RetrievalRequest, RetrievedPassage
from app.retrieval.service import retrieve

RECALL_K = 5
MRR_K = 10


async def _ingest_corpus(
    pool: asyncpg.Pool, embedder: EmbeddingProvider, settings: Settings
) -> dict[str, str]:
    filename_to_id: dict[str, str] = {}
    for doc in CORPUS:
        data = build_pdf(doc.pages)
        result = await ingest_pdf(
            pool,
            embedder,
            settings,
            data=data,
            filename=doc.filename,
            mime_type="application/pdf",
        )
        filename_to_id[doc.filename] = result.document_id
    return filename_to_id


async def evaluate(database_url: str) -> dict[str, Any]:
    settings = get_settings()
    settings.database_url = database_url
    await run_migrations(database_url)

    embedder = build_embedding_provider(settings)
    pool = await create_pool(settings)
    try:
        filename_to_id = await _ingest_corpus(pool, embedder, settings)

        per_question: list[dict[str, Any]] = []
        recall_hits = 0
        reciprocal_sum = 0.0

        for item in EVAL:
            gold_doc = filename_to_id[item.filename]
            response = await retrieve(
                pool,
                embedder,
                RetrievalRequest(query=item.question, top_k=MRR_K),
            )
            ranks = [
                i
                for i, p in enumerate(response.passages)
                if p.document_id == gold_doc and p.page == item.page
            ]
            first_rank = ranks[0] if ranks else None
            in_recall = first_rank is not None and first_rank < RECALL_K
            reciprocal = 1.0 / (first_rank + 1) if first_rank is not None else 0.0

            if in_recall:
                recall_hits += 1
            reciprocal_sum += reciprocal

            per_question.append(
                {
                    "question": item.question,
                    "gold_document": item.filename,
                    "gold_page": item.page,
                    "first_relevant_rank": (first_rank + 1) if first_rank is not None else None,
                    "recall@5_hit": in_recall,
                    "reciprocal_rank": round(reciprocal, 4),
                    "top1": _describe(response.passages[0]) if response.passages else None,
                }
            )

        n = len(EVAL)
        return {
            "embedding_model": embedder.model_id,
            "embedding_dim": embedder.dim,
            "num_questions": n,
            "recall@5": round(recall_hits / n, 4),
            "mrr@10": round(reciprocal_sum / n, 4),
            "per_question": per_question,
        }
    finally:
        await pool.close()


def _describe(passage: RetrievedPassage) -> str:
    return f"{passage.citation} (chunk {passage.chunk_id[:8]})"


def _print_human(report: dict[str, Any]) -> None:
    print("=" * 72)
    print("Veridoc AI — retrieval evaluation (measured)")
    print(f"Embedding model : {report['embedding_model']} (dim {report['embedding_dim']})")
    print(f"Questions       : {report['num_questions']}")
    print(f"Recall@5        : {report['recall@5']}")
    print(f"MRR@10          : {report['mrr@10']}")
    print("-" * 72)
    for q in report["per_question"]:
        status = "HIT " if q["recall@5_hit"] else "miss"
        rank = q["first_relevant_rank"]
        print(f"[{status}] rank={rank!s:>4}  {q['question']}")
    print("=" * 72)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Veridoc AI retrieval evaluation")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--database-url",
        default=get_settings().database_url,
        help="override the database connection string",
    )
    args = parser.parse_args()

    report = await evaluate(args.database_url)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)


if __name__ == "__main__":
    asyncio.run(_main())
