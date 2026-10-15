"""Reproducible retrieval + (optional) generation evaluation.

Retrieval metrics (always): Recall@5 and MRR@10 over the gold (document, page)
citations, computed WITHOUT and WITH reranking so the reranker's effect is
measured, not assumed.

Generation metrics (only with --with-generation): abstention precision/recall,
citation validity, prompt-injection resistance, a transparent keyword proxy for
answer correctness and citation support, and end-to-end latency. These require
an inference provider; when the provider is the deterministic mock, the harness
reports MECHANICS only and explicitly does NOT claim model quality.

Usage:
    python -m app.eval.run                         # retrieval only
    python -m app.eval.run --with-generation       # + generation (uses AI_INFERENCE_PROVIDER)
    python -m app.eval.run --json

Nothing here fabricates numbers; every value is measured on this run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import asyncpg

from app.config import Settings, get_settings
from app.db.migrate import run_migrations
from app.db.pool import create_pool
from app.embeddings import build_embedding_provider
from app.embeddings.base import EmbeddingProvider
from app.eval.corpus import CORPUS, EVAL, RETRIEVAL_EVAL, EvalItem
from app.eval.pdf_build import build_pdf
from app.ingestion.pipeline import ingest_pdf
from app.models import RetrievalRequest
from app.providers import build_provider
from app.rag.service import answer_question
from app.reranking import Reranker, build_reranker
from app.retrieval.service import retrieve

RECALL_K = 5
MRR_K = 10


async def _ingest_corpus(
    pool: asyncpg.Pool, embedder: EmbeddingProvider, settings: Settings
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for doc in CORPUS:
        result = await ingest_pdf(
            pool,
            embedder,
            settings,
            data=build_pdf(doc.pages),
            filename=doc.filename,
            mime_type="application/pdf",
        )
        mapping[doc.filename] = result.document_id
    return mapping


def _gold_pairs(item: EvalItem, filename_to_id: dict[str, str]) -> set[tuple[str, int]]:
    return {(filename_to_id[f], p) for f, p in item.gold}


async def _retrieval_metrics(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    settings: Settings,
    filename_to_id: dict[str, str],
    reranker: Reranker | None,
) -> dict[str, Any]:
    recall_sum = 0.0
    reciprocal_sum = 0.0
    for item in RETRIEVAL_EVAL:
        gold = _gold_pairs(item, filename_to_id)
        resp = await retrieve(
            pool,
            embedder,
            RetrievalRequest(query=item.question, top_k=MRR_K, rerank=reranker is not None),
            reranker,
            rerank_candidate_k=settings.rerank_candidate_k,
        )
        ranks = [
            i
            for i, p in enumerate(resp.passages)
            if (p.document_id, p.page) in gold
        ]
        # True set-based Recall@5: the fraction of this item's gold pairs that
        # appear in the top-K (a multi-gold "compare" item is only fully recalled
        # when ALL its gold pages are retrieved, not just the first).
        if gold:
            top_k_pairs = {(p.document_id, p.page) for p in resp.passages[:RECALL_K]}
            recall_sum += len(top_k_pairs & gold) / len(gold)
        # MRR@10 uses the rank of the first relevant passage (conventional).
        first = ranks[0] if ranks else None
        reciprocal_sum += 1.0 / (first + 1) if first is not None else 0.0

    n = len(RETRIEVAL_EVAL)
    return {"recall@5": round(recall_sum / n, 4), "mrr@10": round(reciprocal_sum / n, 4)}


async def _generation_metrics(
    pool: asyncpg.Pool,
    embedder: EmbeddingProvider,
    reranker: Reranker | None,
    provider: Any,
    settings: Settings,
) -> dict[str, Any]:
    # Confusion counts for abstention.
    abstain_tp = abstain_fp = abstain_fn = 0
    citation_valid = 0
    correct = support = answerable = 0
    injection_total = injection_resisted = 0
    latencies: list[float] = []
    per_item: list[dict[str, Any]] = []

    for item in EVAL:
        start = time.perf_counter()
        outcome = await answer_question(
            pool, embedder, reranker, provider, settings,
            question=item.question, document_ids=[], top_k=5, rerank=reranker is not None,
        )
        latency = time.perf_counter() - start
        latencies.append(latency)

        answer_lc = outcome.answer.lower()

        if item.expect_abstain and outcome.abstained:
            abstain_tp += 1
        elif item.expect_abstain and not outcome.abstained:
            abstain_fn += 1
        elif not item.expect_abstain and outcome.abstained:
            abstain_fp += 1

        if outcome.invalid_citation_count == 0:
            citation_valid += 1

        if item.injection_canary is not None:
            injection_total += 1
            if item.injection_canary.lower() not in answer_lc:
                injection_resisted += 1

        if not item.expect_abstain and item.answer_keywords:
            answerable += 1
            if all(k.lower() in answer_lc for k in item.answer_keywords):
                correct += 1
            cited_text = " ".join(c.snippet.lower() for c in outcome.citations)
            if any(k.lower() in cited_text for k in item.answer_keywords):
                support += 1

        per_item.append(
            {
                "id": item.id,
                "category": item.category,
                "abstained": outcome.abstained,
                "invalid_citations": outcome.invalid_citation_count,
                "num_citations": len(outcome.citations),
                "latency_s": round(latency, 4),
            }
        )

    abstain_prec = abstain_tp / (abstain_tp + abstain_fp) if (abstain_tp + abstain_fp) else None
    abstain_rec = abstain_tp / (abstain_tp + abstain_fn) if (abstain_tp + abstain_fn) else None

    return {
        "provider": provider.name,
        "mock": provider.is_mock,
        "note": (
            "MECHANICS ONLY — provider is the deterministic mock; answer "
            "correctness/support are NOT a model-quality result."
            if provider.is_mock
            else "measured with a real inference provider"
        ),
        "citation_validity_rate": round(citation_valid / len(EVAL), 4),
        "abstention_precision": None if abstain_prec is None else round(abstain_prec, 4),
        "abstention_recall": None if abstain_rec is None else round(abstain_rec, 4),
        "injection_resistance": (
            round(injection_resisted / injection_total, 4) if injection_total else None
        ),
        "answer_correctness_rate": round(correct / answerable, 4) if answerable else None,
        "citation_support_rate": round(support / answerable, 4) if answerable else None,
        "mean_latency_s": round(sum(latencies) / len(latencies), 4),
        "per_item": per_item,
    }


async def evaluate(
    database_url: str, *, with_generation: bool, reranker_provider: str
) -> dict[str, Any]:
    settings = get_settings()
    settings.database_url = database_url
    settings.reranker_provider = reranker_provider
    await run_migrations(database_url)

    embedder = build_embedding_provider(settings)
    pool = await create_pool(settings)
    try:
        filename_to_id = await _ingest_corpus(pool, embedder, settings)

        # `--reranker` selects the second-stage model (default deterministic:
        # reproducible, no downloads). The first-stage (no-rerank) leg is always
        # the RRF baseline.
        reranker: Reranker | None = build_reranker(settings)
        no_rerank = await _retrieval_metrics(pool, embedder, settings, filename_to_id, None)
        with_rerank = (
            await _retrieval_metrics(pool, embedder, settings, filename_to_id, reranker)
            if reranker is not None
            else {"status": "reranker unavailable"}
        )

        report: dict[str, Any] = {
            "embedding_model": embedder.model_id,
            "embedding_dim": embedder.dim,
            "num_retrieval_questions": len(RETRIEVAL_EVAL),
            "num_total_questions": len(EVAL),
            "reranker_model": reranker.model_id if reranker else None,
            "retrieval_without_rerank": no_rerank,
            "retrieval_with_rerank": with_rerank,
        }

        if with_generation:
            provider = build_provider(settings)
            report["generation"] = await _generation_metrics(
                pool, embedder, reranker, provider, settings
            )
        else:
            report["generation"] = {
                "status": "NOT RUN",
                "reason": "run with --with-generation and configure AI_INFERENCE_PROVIDER",
            }
        return report
    finally:
        await pool.close()


def _print_human(r: dict[str, Any]) -> None:
    print("=" * 72)
    print("Veridoc AI — evaluation (measured)")
    print(f"Embedding : {r['embedding_model']} (dim {r['embedding_dim']})")
    print(f"Reranker  : {r['reranker_model']}")
    print(f"Retrieval questions: {r['num_retrieval_questions']} / total {r['num_total_questions']}")
    print("-" * 72)
    nr, wr = r["retrieval_without_rerank"], r["retrieval_with_rerank"]
    print(f"Retrieval  no-rerank : Recall@5={nr['recall@5']}  MRR@10={nr['mrr@10']}")
    if "recall@5" in wr:
        print(f"Retrieval  rerank    : Recall@5={wr['recall@5']}  MRR@10={wr['mrr@10']}")
    else:
        print(f"Retrieval  rerank    : {wr.get('status')}")
    print("-" * 72)
    g = r["generation"]
    if g.get("status") == "NOT RUN":
        print(f"Generation : NOT RUN ({g['reason']})")
    else:
        print(f"Generation provider: {g['provider']} (mock={g['mock']})")
        print(f"  {g['note']}")
        print(f"  citation_validity_rate : {g['citation_validity_rate']}")
        print(f"  abstention_precision   : {g['abstention_precision']}")
        print(f"  abstention_recall      : {g['abstention_recall']}")
        print(f"  injection_resistance   : {g['injection_resistance']}")
        print(f"  answer_correctness_rate: {g['answer_correctness_rate']}")
        print(f"  citation_support_rate  : {g['citation_support_rate']}")
        print(f"  mean_latency_s         : {g['mean_latency_s']}")
    print("=" * 72)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Veridoc AI evaluation")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--with-generation",
        action="store_true",
        help="also run grounded generation eval (uses the configured provider)",
    )
    parser.add_argument("--database-url", default=get_settings().database_url)
    parser.add_argument(
        "--reranker",
        default="deterministic",
        choices=["none", "deterministic", "cross-encoder"],
        help="second-stage reranker for the with-rerank comparison",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=None,
        help="regression gate: exit non-zero if no-rerank Recall@5 is below this floor",
    )
    parser.add_argument(
        "--min-mrr",
        type=float,
        default=None,
        help="regression gate: exit non-zero if no-rerank MRR@10 is below this floor",
    )
    args = parser.parse_args()

    report = await evaluate(
        args.database_url,
        with_generation=args.with_generation,
        reranker_provider=args.reranker,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)

    # Deterministic eval, so a floor is a safe regression gate (never flakes).
    # Checked on the no-rerank RRF baseline (the stable leg).
    nr = report["retrieval_without_rerank"]
    failures: list[str] = []
    if args.min_recall is not None and nr["recall@5"] < args.min_recall:
        failures.append(f"recall@5 {nr['recall@5']} < floor {args.min_recall}")
    if args.min_mrr is not None and nr["mrr@10"] < args.min_mrr:
        failures.append(f"mrr@10 {nr['mrr@10']} < floor {args.min_mrr}")
    if failures:
        raise SystemExit("Retrieval regression gate FAILED: " + "; ".join(failures))


if __name__ == "__main__":
    asyncio.run(_main())
