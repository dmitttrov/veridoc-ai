# Veridoc AI — Retrieval Evaluation (Phase 2)

Measured retrieval quality over a **synthetic, fictional** corpus. Every number
here is produced by the committed, re-runnable script `app/eval/run.py` — none
is hand-written or estimated.

## Method

- **Corpus** (`app/eval/corpus.py`): two fictional reports, 11 pages total
  (Acme Robotics FY2023, 6 pages; Globex Logistics Q2 2024, 5 pages). Pages are
  rendered to real PDFs (reportlab) and ingested through the full pipeline
  (validate → normalize → chunk → embed → store).
- **Questions**: 10, each with a known gold `(document, page)` citation.
- **Relevance**: a retrieved passage is relevant iff its `(document_id, page)`
  equals the gold pair — i.e. retrieval surfaced the correct **page-level
  evidence**. This directly reflects the product goal (traceable citations).
- **Metrics**:
  - **Recall@5** — fraction of questions with a relevant passage in the top 5.
  - **MRR@10** — mean reciprocal rank of the first relevant passage in the top 10.
- **Retrieval**: hybrid (PostgreSQL FTS + pgvector cosine) fused with RRF (k=60).

Reproduce:

```bash
# against a running Postgres+pgvector (see infra/):
AI_DATABASE_URL=postgresql://veridoc:veridoc@localhost:5432/veridoc \
AI_EMBEDDING_PROVIDER=deterministic \
python -m app.eval.run
```

## Measured results

Run on 2026-10-13, 10 questions, hybrid retrieval.

| Embedding provider | Model (dim) | Recall@5 | MRR@10 |
| ------------------ | ----------- | -------- | ------ |
| deterministic | `veridoc-deterministic-emb-v1` (384) | **1.00** | **1.00** |
| sentence-transformers | `all-MiniLM-L6-v2` (384) | **1.00** | **0.833** |

Per-question detail is printed by the script (and emitted as JSON with
`--json`). With the real model, the first relevant passage was ranked #1 for 7
of 10 questions and #2–#3 for the rest.

## Honest interpretation (important)

- **This corpus is small and keyword-distinct by design.** It exists to prove
  the pipeline end-to-end and to make the metric meaningful and reproducible —
  **not** to demonstrate production-grade retrieval quality. Perfect/near-perfect
  scores here reflect task easiness, not a general capability claim.
- The **deterministic** provider is feature-hashing over tokens, so it rewards
  exact lexical overlap; since the questions reuse corpus vocabulary it scores
  very highly. It is ideal for reproducible CI, but it is **not** a semantic
  model.
- The **real** `all-MiniLM-L6-v2` model is genuinely semantic and occasionally
  ranks a related-but-wrong page above the gold page (hence MRR < 1.0). This is
  the more realistic signal.
- We do **not** extrapolate these numbers to real filings. A larger, adversarial
  evaluation set and a reranking stage are Phase 3 work (see `ROADMAP.md`).

## Threats to validity

- Small N (10 questions, 11 pages): high variance; not representative of real
  10-K/interim filings with tables and dense numerics.
- Synthetic text is cleaner than scanned or table-heavy PDFs.
- Gold is page-level, not span-level; it rewards finding the right page, not the
  exact sentence.
