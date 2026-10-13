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

---

# Phase 4C — real-world generalization (SEC EDGAR)

**Goal:** test whether the LoRA adapter generalizes to *real* financial figures
or merely memorized the synthetic template.

## Real benchmark (built, authoritative)

A 122-example extraction test set was built from the **SEC EDGAR XBRL
`companyconcept` API** (public-domain US government data) — exact reported
values, units, and fiscal periods tied to real 10-K filings (form + accession).
Ground truth is the XBRL fact itself; **no figure was typed from memory and no
model output is used as ground truth.**

- Companies (6, cross-sector): Apple, Microsoft, JPMorgan Chase, Johnson &
  Johnson, Walmart, Exxon Mobil.
- Metrics (8): total revenue, operating income, net income, total assets, total
  liabilities, cash & equivalents, operating cash flow, stockholders' equity.
- Categories: answerable 44, unanswerable 44, multi_page 20, conflicting 14
  (real restatements, e.g. JPMorgan FY2008 operating cash flow $23,098M →
  restated $23,930M).
- Build is reproducible: `python -m veridoc_ft.realeval.dataset`. Fixtures stay
  out of Git (SEC data is public-domain/redistributable, but kept private by
  default per the brief); the builder + provenance are committed.

Evidence passages state the real figure in filing style (`$391,035 million`,
`$0.120 billion`, accounting negatives) and the scorer uses a dedicated
**financial value normalizer** (currency symbols, commas, millions/billions,
parentheses-negatives) so e.g. "391,035"/"USD millions", "391.035 billion", and
the raw XBRL integer all compare equal. Citation **validity** (marker is a
provided passage) is scored separately from citation **support** (the cited
passage actually contains the value).

## Phase 4C.1 — executed on the GPU server (measured)

Connectivity was restored; artifact integrity re-verified **before** evaluation:
adapter-v1 SHA-256 `c9a492bd…bb67` (unchanged/immutable), base `Qwen/Qwen3-0.6B`
@ `c1899de…`, synthetic dataset v1 hashes unchanged, Phase 4B reports preserved.

**Pre-model benchmark audit** cross-checked every supported gold value against
the authoritative XBRL fact (by cik + accession + period-end, `fp=FY`,
form 10-K): **151/151 match**, periods 151/151 consistent, conflicting 24/24
well-formed, unanswerable evidence genuinely lacks the asked metric. The audit
caught and fixed two pre-model defects (no model had seen the data): a
conflation of annual vs. quarterly facts in the "conflicting" generator, and a
`$(…)` currency+parenthesis negative-parsing gap in the normalizer. The audit
also **reclassified the evidence honestly**:

| Evidence type | Count |
| --- | --- |
| (1) authentic filing excerpt | **0** |
| (2) XBRL-derived structured | 0 |
| (3) synthetic / templated prose (real XBRL values) | **239** |

> All 239 evidence passages are **templated prose wrapping authoritative XBRL
> figures**. This tests generalization to real companies / scales / values /
> periods / restatements — it does **NOT** test authentic filing *text* (tables,
> footnotes, prose). **Real filing-text generalization remains untested.**

Frozen benchmark: 239 examples (answerable 88, unanswerable 88, multi_page 39,
conflicting 24), sha256 `9f9c3495…`. Oracle-evidence mode; greedy decoding
identical to Phase 4B; same prompt/schema/normalization for base and adapter.

### Measured results (n=239, 1× RTX PRO 6000 Blackwell)

| Metric | Base Qwen3-0.6B | + adapter | Paired Δ (95% CI, bootstrap) |
| --- | --- | --- | --- |
| JSON parse success | 1.000 | 1.000 | — |
| schema_valid | 0.778 | 1.000 | **+0.222 [0.172, 0.276]** |
| value_exact (n=151) | 0.920 | 0.980 | **+0.060 [0.013, 0.113]** |
| metric_exact | 0.801 | 0.841 | **+0.040 [0.013, 0.073]** |
| unit_correct | 1.000 | 1.000 | — |
| period_correct | 1.000 | 1.000 | — |
| citation_valid | 1.000 | 1.000 | — |
| citation_support | 1.000 | 1.000 | — |
| abstention precision / recall | 1.00 / 0.602 | 1.00 / 0.864 | — |
| mean latency (greedy) | 1.03 s | 1.16 s | — |

All three headline improvements are credible by **paired bootstrap** on the same
239 examples (10k resamples; per-example difference CI excludes 0). Base peak
1.26 GB, adapter 1.31 GB.

### Interpretation — genuine improvements, with honest caveats

Per-category (base → adapter):

- **conflicting** value_exact **14/24 → 24/24**: the base often returns the
  original figure; the adapter learned to prefer the restated value. Real gain.
- **unanswerable** schema-valid **35/88 → 88/88** and abstention **53/88 →
  76/88**: the base emits schema-invalid JSON when abstaining; the adapter
  abstains cleanly and more often. Real gain.
- **answerable** value_exact **87/88 → 86/88** and **multi_page** 38/39 → 38/39:
  essentially flat — the base was already strong here.

This is **generalization, not pure template memorization**: the adapter improves
on real SEC figures (billions-scale, real companies/periods) it never saw,
chiefly via schema-format discipline, restatement preference, and cleaner
abstention.

**Regressions / failures (preserved):**

- **Negative values (regression):** on JPMorgan's negative operating cash flow
  (`$(42,012) million`), the adapter mangles the value/unit (e.g. `"unit":
  "$(USD millions…"`) and is **worse than the base** (3/3 such cases wrong). It
  was trained only on positive synthetic values — sign/parenthesis handling did
  not transfer. Sign errors are high-impact for financial use.
- **Abstention gap (12 cases):** the adapter answers instead of abstaining when
  the asked metric is a near-synonym of the evidence metric ("cash and cash
  equivalents" vs "net cash from operating activities"), confusing the two.
- **Evidence realism:** templated prose only — authentic filing-text extraction
  (tables, footnotes, OCR, messy layout) is **not measured**.

> Do not read these numbers as broad real-world financial competence: they are
> extraction accuracy on XBRL-derived values in clean templated sentences.

## Release decision: **A — experimental release justified (with documented limits)**

The adapter shows credible, paired improvements over the base on real
SEC-derived values (schema validity, restatement extraction, abstention) and is
a small **domain-adapted structured-extraction** adapter — **not** a financial
reasoning or advice model. Experimental release is justified **only** if the
model card prominently documents: (a) evaluation was on XBRL-derived values in
templated prose, so authentic filing-text generalization is **untested**; (b) a
**regression on negative/parenthesized values**; (c) an abstention gap on
near-synonym metrics; (d) no real-money/advice use. The remaining blocker for a
*non-experimental* release is an authentic-filing-text evaluation.

Reproduce:

```bash
python -m veridoc_ft.realeval.dataset --out data/realeval --built-at <date>
python scripts/audit_realeval.py            # pre-model integrity audit
python -m veridoc_ft.realeval.evaluate --data data/realeval/real_test.jsonl \
    --out artifacts/real_base.json                                   # base
python -m veridoc_ft.realeval.evaluate --data data/realeval/real_test.jsonl \
    --adapter artifacts/adapter-v1 --out artifacts/real_adapter.json  # adapter
python scripts/report.py --baseline artifacts/real_base.json \
    --adapter artifacts/real_adapter.json --out artifacts/real_comparison.json
```

End-to-end **RAG** real-eval (retrieval + extraction over ingested real
documents) still needs the services/ai stack and is not run here.
