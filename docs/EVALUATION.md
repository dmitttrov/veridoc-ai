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

## Phase 4 — fine-tuning (extraction) benchmark status

A separate, reproducible extraction benchmark lives in `training/` (base vs LoRA
adapter on a held-out, family-split synthetic test set; metrics: JSON parse,
schema validity, exact metric/value/unit/period, evidence-ref validity,
abstention precision/recall, injection resistance, latency; Wilson 95% CIs on
the base-vs-adapter comparison).

**Status: EXECUTED (Phase 4B) on 1× NVIDIA RTX PRO 6000 Blackwell (96 GB),
driver 580.178.04, torch 2.11.0+cu128, bf16.** GPU 0 only; the second GPU and
all shared services were left untouched. Dataset built deterministically
(186/60/42; test split SHA-256 `e3f80775…22f6`).

Decoding: greedy (temperature 0), `enable_thinking=False`, Qwen3 chat template,
identical for base and adapter. n = 42 held-out test examples.

| Metric | Base Qwen3-0.6B | + LoRA adapter | Paired Δ (95% CI, bootstrap) |
| --- | --- | --- | --- |
| JSON parse success | 1.000 | 1.000 | — |
| schema_valid | 0.714 | 1.000 | **+0.286 [0.167, 0.429]** |
| value_exact (n=28) | 0.750 | 1.000 | **+0.250 [0.107, 0.429]** |
| metric_exact | 0.750 | 1.000 | **+0.250 [0.107, 0.429]** |
| unit_correct | 0.750 | 1.000 | — |
| period_correct | 1.000 | 1.000 | — |
| evidence_ref_valid | 1.000 | 1.000 | 0.000 [0, 0] |
| abstention precision / recall | 1.00 / 0.857 | 1.00 / 1.00 | — |
| injection_resistance | 1.000 | 1.000 | — |
| mean latency (greedy) | 0.99 s | 1.12 s | — |

**Paired comparison (not Wilson overlap):** credibility is judged by a paired
bootstrap over the *same* 42 examples (10k resamples). schema_valid, value_exact
and metric_exact each improve with a 95% CI of the per-example difference that
excludes 0; evidence_ref_valid was already 1.0 (no change).

Per-category (base → adapter): **answerable** 14/14 → 14/14 (already solved);
**conflicting** value_exact 0/7 → 7/7 (base ignored the restatement; adapter
learned to prefer it); **injection** 7/7 → 7/7 (both resist); **unanswerable**
schema-valid 2/14 → 14/14 and abstention 12/14 → 14/14 (adapter emits
schema-valid abstentions).

Training: 36 optimizer steps (3 epochs) in **92.9 s**, **peak 2.23 GB** VRAM,
adapter **39 MB**, final train loss 0.18, val loss 0.0014.

> ⚠️ **Synthetic benchmark, not real financial-document performance.** The
> corpus is small, fictional, and templated; the adapter fit it almost perfectly
> (val loss ~0.001), so the near-ceiling adapter scores mainly reflect learning
> the dataset's output conventions (JSON schema, restatement preference,
> schema-valid abstention). This is a controlled proof-of-pipeline with a
> credible, honestly-measured improvement on *this* benchmark — **not** evidence
> of real-filing capability. Reproduce with the commands in `training/README.md`.

## Threats to validity

- Small N (15 questions, 16 pages): high variance; not representative of real
  10-K/interim filings with tables and dense numerics.
- Synthetic text is cleaner than scanned or table-heavy PDFs.
- Gold is page-level, not span-level.
- The deterministic embedding/reranker are reproducibility stand-ins, not
  semantic models; the real cross-encoder row is the more realistic signal.
- Keyword proxies for correctness/support are coarse and do not capture
  paraphrase or numerical reasoning.
