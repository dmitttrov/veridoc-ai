# Veridoc AI — Evaluation

Measured retrieval and generation-mechanics results over a **synthetic,
fictional** corpus. Every number here is produced by the committed, re-runnable
script `app/eval/run.py` — none is hand-written or estimated.

## Corpus & method

- **Corpus** (`app/eval/corpus.py`): three fictional reports, 16 pages total
  (Acme Robotics FY2023, Globex Logistics Q2 2024, Initech Semiconductors
  FY2023). Rendered to deterministic PDFs (reportlab `invariant=1`) and ingested
  through the full pipeline.
- **Questions** (15): categories include direct, paraphrased, comparison
  (multi-page), conflicting evidence (restated figure), unanswerable (must
  abstain), and prompt-injection (embedded "ignore instructions" text).
- 13 of the 15 have gold `(document, page)` citations and are used for
  retrieval metrics; the 2 unanswerable ones are used for abstention.
- **Relevance**: a retrieved passage is relevant iff its `(document_id, page)`
  matches a gold pair (page-level evidence found).
- **Retrieval**: hybrid (Postgres FTS + pgvector cosine) fused with RRF.
  Vector search is **exact** (no ANN index at this scale — see ADR-0016), which
  makes results fully reproducible run-to-run.

Reproduce:

```bash
AI_DATABASE_URL=postgresql://veridoc:veridoc@localhost:5432/veridoc \
AI_EMBEDDING_PROVIDER=deterministic \
python -m app.eval.run                         # retrieval only
python -m app.eval.run --with-generation       # + generation (uses the provider)
python -m app.eval.run --reranker cross-encoder # real cross-encoder second stage
```

## Measured results

Run on 2026-10-13 with **deterministic** embeddings
(`veridoc-deterministic-emb-v1`, 384-dim). Reproducible (identical across runs).

### Retrieval (13 gold questions)

| Configuration | Recall@5 | MRR@10 |
| ------------- | -------- | ------ |
| Hybrid, no rerank (RRF)                               | 1.000 | 0.765 |
| + deterministic reranker (`veridoc-deterministic-reranker-v1`) | 1.000 | 0.814 |
| + cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`)       | 0.923 | 0.859 |

**Reranker — improvement and regression, honestly.** Both rerankers improve
MRR@10 (better top ranking). The real cross-encoder improves MRR the most
(0.765→0.859) but **reduces Recall@5** (1.000→0.923): on one question it promoted
a different page into the top-5 and pushed the gold page to rank 6. Reranking is
not a pure win — it trades recall for precision-at-top, and that trade must be
measured per use case, not assumed.

### Generation mechanics (mock provider)

Run with `--with-generation` and `AI_INFERENCE_PROVIDER=mock`.

> ⚠️ **These are MECHANICS, not model quality.** The provider is the
> deterministic mock, so answer-correctness/support numbers reflect the mock's
> placeholder text, **not** a real model. Real-model generation quality is **NOT
> evaluated** in this phase (no local/real inference server was available).

| Metric | Value | Interpretation |
| ------ | ----- | -------------- |
| citation validity rate | 1.000 | no fabricated citations survived verification |
| injection resistance | 1.000 | embedded "BANANA" instruction never surfaced |
| abstention recall | 0.000 | the mock cannot judge sufficiency; it abstains only when retrieval is empty |
| abstention precision | n/a | mock produced no abstentions on these items |
| answer correctness (keyword) | 0.077 | expected — the mock emits placeholder text, not real figures |
| citation support (keyword) | 0.846 | cited passages usually contained the expected fact |
| mean latency | ~0.015 s | mock has no network/model cost |

Citation **validity** (the cited marker maps to a retrieved passage) is verified;
citation **support** (the passage actually substantiates the claim) is reported
separately and is only a keyword proxy. A valid citation does **not** prove the
claim is supported.

## Generation evaluation status

**Real-model generation evaluation: NOT RUN.** No GPU/real inference server was
available this phase. The harness is complete and reproducible: point
`AI_INFERENCE_PROVIDER=openai_compatible` + `AI_INFERENCE_BASE_URL` at a local
OpenAI-compatible server (e.g. vLLM) and run `--with-generation` to obtain
answer-correctness, support, and abstention metrics with a real model. The RAG
*mechanics* (grounding, citation validity, fabricated-citation rejection,
abstention-on-empty, injection resistance) are covered by DB-backed tests and by
the mock-provider mechanics run above.

## Threats to validity

- Small N (15 questions, 16 pages): high variance; not representative of real
  10-K/interim filings with tables and dense numerics.
- Synthetic text is cleaner than scanned or table-heavy PDFs.
- Gold is page-level, not span-level.
- The deterministic embedding/reranker are reproducibility stand-ins, not
  semantic models; the real cross-encoder row is the more realistic signal.
- Keyword proxies for correctness/support are coarse and do not capture
  paraphrase or numerical reasoning.
