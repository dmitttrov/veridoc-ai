# Veridoc AI — Roadmap

A 14-day milestone plan. Day 1 is the Phase 1 vertical slice (this milestone,
**complete**). Each subsequent milestone lists concrete acceptance criteria.
Dates are relative (Day N) so the plan stays valid regardless of start date.

> Scope discipline: no new infrastructure is introduced unless a milestone's
> acceptance criteria require it, and every such decision is recorded in
> `DECISIONS.md`.

---

## Day 1 — Phase 1 vertical slice ✅ (done)

**Goal:** End-to-end streaming from React → NestJS → FastAPI with a deterministic
mock, typed contracts, tests, and CI.

**Acceptance criteria**
- [x] `apps/web`, `apps/api`, `services/ai`, `packages/contracts`, `infra`, `docs`.
- [x] `POST /api/chat` validates input and streams SSE end-to-end.
- [x] Deterministic `MockProvider`; **MOCK MODE** visible in the UI.
- [x] Health endpoints for gateway and AI service.
- [x] Tests pass for all three apps; lint + typecheck clean.
- [x] Docker Compose for web/api/ai; runs with no GPU and no paid services.
- [x] GitHub Actions CI (lint, typecheck, test).

---

## Days 2–5 — Phase 2: ingestion + hybrid retrieval ✅ (done)

**Goal:** Ingest real PDFs with page-level provenance into PostgreSQL+pgvector
and retrieve real evidence via hybrid search.

**Acceptance criteria**
- [x] Compose adds a Postgres+pgvector service; versioned migrations create
      `documents`, `document_pages`, `document_chunks`, `ingestion_runs`.
- [x] Secure PDF ingestion (pypdf): signature/size/page-count/encryption/
      malformed checks, processing timeout, deterministic normalize + chunk with
      `(document_id, page, char_span)` provenance; CLI + gateway upload.
- [x] Upload endpoint on the gateway enforces type/size limits (see SECURITY).
- [x] Pluggable embeddings (deterministic + local sentence-transformers),
      fixed 384-dim, model identity recorded, dimension mixing rejected.
- [x] Hybrid retrieval: Postgres FTS + pgvector cosine + RRF; configurable top-k;
      document filtering; traceable page-level citations.
- [x] Idempotent ingestion; transactional store with rollback.
- [x] Tests for uploads, encrypted/malformed/empty PDFs, stable chunk ids/offsets,
      idempotency, rollback, dimension mismatch, keyword/vector/hybrid retrieval,
      filtering, citation correctness, gateway error propagation.
- [x] Reproducible evaluation (`python -m app.eval.run`) over a synthetic corpus
      reporting **measured** Recall@5 and MRR@10 — see `docs/EVALUATION.md`.

Deferred to Phase 3: cross-encoder reranking.

---

## Phase 3 — Reranking + source-grounded generation ✅ (done)

**Goal:** Add a reranker and the first real generation grounded in retrieved
passages, with verifiable citations.

**Acceptance criteria**
- [x] Cross-encoder reranker (pluggable; deterministic test reranker; explicit
      fallback) reorders the RRF top-N → top-k; scores kept distinct from RRF.
- [x] Evaluation with/without reranking, measured (see EVALUATION.md): MRR@10
      improves; cross-encoder trades a little Recall@5 — reported honestly.
- [x] `OpenAICompatibleProvider` (local server / vLLM) behind the provider seam;
      mock default/CI; never silently falls back; fake-server streaming/failure
      tests.
- [x] Grounded RAG: untrusted-evidence framing, abstention, citation
      verification (fabricated refs rejected), verify-then-stream.
- [x] Exact vector search for reproducibility (ADR-0016); deterministic fixtures
      (ADR-0017).
- [x] Frontend: grounded-answer mode with mock/real badge, cited sources,
      abstention/error states, evidence-vs-answer distinction; mock chat +
      retrieval modes preserved.
- [x] Quality gates pass; Docker Compose build + smoke test.

Not done this phase (no GPU/real inference available): real-model generation
quality metrics — harness exists and is reproducible; marked NOT RUN.

---

## Phase 4 — LoRA fine-tuning + evaluation infrastructure ✅ (infra done)

**Goal:** Produce a small domain-adapted adapter for structured financial-fact
extraction and measure it honestly against a base-model baseline, before any
Hugging Face publication.

**Done (implemented + CPU-verified)**
- [x] Base model selected + pinned: `Qwen/Qwen3-0.6B` @ rev `c1899de…` (ADR-0021).
- [x] Strict Pydantic extraction schema (supported-vs-abstain invariant); prompt
      with untrusted-evidence framing; no invented values/markers.
- [x] Reproducible synthetic dataset pipeline (`training/veridoc_ft/dataset.py`):
      answerable / unanswerable / conflicting / injection; dedup; **family split**
      (no leakage); versioned + per-split SHA-256. Data git-ignored.
- [x] LoRA SFT pipeline (PEFT + Transformers Trainer): seeds, pinned revision,
      grad accumulation, gradient checkpointing, checkpoints/resume, loss curve,
      GPU-memory reporting; no auto-upload.
- [x] Baseline + adapter evaluation on the held-out set, identical decoding;
      JSON/schema/field/evidence/abstention/injection/latency metrics; Wilson CIs
      for base-vs-adapter comparison.
- [x] Configurable serving path (base vs adapter vs mock) via the OpenAI-compatible
      provider; mock preserved.
- [x] Draft model card, dataset card, release checklist (nothing published).
- [x] No-network **CPU training smoke test** (tiny random Qwen3) in the suite.

## Phase 4B — first GPU experiment ✅ (executed)

Ran the full pipeline on 1× RTX PRO 6000 Blackwell (GPU 0; isolated env; shared
services untouched):
- [x] Preflight; isolated CUDA-12.8 venv; bf16 + Qwen3 load + PEFT init verified.
- [x] Baseline on the full 42-example test set (schema_valid 0.714, value_exact 0.75).
- [x] 10-step pilot (finite loss, checkpoint save + reload, no OOM).
- [x] Full LoRA (3 epochs, 36 steps, 92.9 s, peak 2.23 GB, 39 MB adapter).
- [x] Adapter eval + **paired-bootstrap** comparison: schema_valid 0.714→1.0,
      value_exact 0.75→1.0, metric_exact 0.75→1.0 (all credible); evidence_ref
      already 1.0.
- [x] Independent adapter load + representative inference (matches gold).

Result is a **credible improvement on synthetic/templated data only** — not a
real-filing claim. See `docs/EVALUATION.md`.

## Phase 4C — real-world generalization benchmark ✅ (built; eval blocked)

- [x] Built a 122-example **real** extraction benchmark from SEC EDGAR XBRL
      (authoritative, public-domain) across 6 cross-sector companies / 8 metrics
      / 4 categories (incl. real restatements).
- [x] Oracle-eval harness + financial value normalizer (currency / millions /
      billions / parentheses) + citation validity-vs-support scoring; unit-tested.
- [x] **Measured base-vs-adapter real eval — EXECUTED (Phase 4C.1).** 239 SEC
      examples; pre-model audit 151/151 XBRL cross-check; adapter credibly
      improves schema_valid 0.778→1.0, value_exact 0.920→0.980, metric_exact
      0.801→0.841 (paired bootstrap). Generalizes, not just memorizes. Regression
      on negative values + abstention gap documented. **Decision: A (experimental).**
- [ ] Authentic filing-TEXT eval (templated-prose evidence only so far) — blocks
      a non-experimental release.
- [ ] End-to-end RAG real-eval (retrieval + extraction) over ingested real docs.

## Phase 4D — adapter-v2: targeted fixes ✅ (done)

- [x] dataset v2 (= v1 + targeted: negatives/parenthesized, negative cash flow,
      billions, near-synonym disambiguation + abstention); family-split, hashed.
- [x] dev-only regression suite (12 examples, separate from the frozen benchmark).
- [x] adapter-v2 trained from the pinned base (same LoRA), 137 s, peak 2.23 GB,
      checksum `165518747f28…`. v1 kept immutable.
- [x] base vs v1 vs v2 on dev suite + frozen 239 SEC set; paired bootstrap.
      v2 fixes signed values (3/3) + near-synonym abstention (12/12), **no
      regressions**; value_exact 0.980→1.0, metric_exact 0.841→1.0,
      abstention_recall 0.864→1.0. **Decision: prefer v2 (experimental, A).**
- [ ] Authentic filing-text eval still NOT done — the remaining release blocker;
      frozen-set gains for v2 are a targeted regression check, not independent
      generalization.

## Phase 5 (planned) — Run the real eval → decision → (approved) publication

Run the Phase 4C commands on the GPU server to get measured base-vs-adapter
real-world numbers → finalize the release decision → if justified, execute the
release checklist (adapter-only HF upload) once approved; plus OpenTelemetry,
rate limiting, and a containerized vLLM serving path for the adapter.

---

## Days 8–9 — Source-grounded generation (first real model)

**Goal:** Swap the mock for a real open-weight model via an OpenAI-compatible
provider, grounded strictly in retrieved passages.

**Acceptance criteria**
- [ ] `OpenAICompatibleProvider` in `services/ai` targets a configurable
      base URL (local server); mock remains the default and CI backend.
- [ ] Prompt assembles retrieved passages with citation markers; the model is
      instructed to answer only from context and to abstain otherwise.
- [ ] MOCK MODE badge turns off automatically when a real provider is active.
- [ ] Prompt-injection mitigations from SECURITY applied to retrieved text.

---

## Days 10–11 — Evaluation harness (RAG quality)

**Goal:** Quantify answer faithfulness and citation accuracy.

**Acceptance criteria**
- [ ] Committed eval set + script producing faithfulness and
      citation-precision/recall metrics.
- [ ] Results written to a report artifact; reproducible via one command.
- [ ] Results published in the repo only as computed (never hand-edited).

---

## Days 12–13 — Model fine-tuning (LoRA/QLoRA)

**Goal:** A small domain-adapted adapter over a suitable open-weight base.

**Acceptance criteria**
- [ ] Reproducible PEFT/LoRA training script with pinned configs and dataset
      provenance (see `MODEL_STRATEGY.md`); no datasets/weights committed.
- [ ] Before/after evaluation on the Day 10–11 harness, honestly reported.
- [ ] Draft Hugging Face **model card** (not yet published) with intended use,
      limitations, training data provenance, and eval methodology.

---

## Day 14 — Production hardening + release prep

**Goal:** Make it robust and presentable; prepare (not execute) publication.

**Acceptance criteria**
- [ ] OpenTelemetry traces across gateway → AI; structured request logging.
- [ ] Rate limiting and payload limits on the gateway edge.
- [ ] Containerized model-serving path documented (vLLM), GPU-optional.
- [ ] Release checklist for GitHub + Hugging Face prepared; **nothing pushed**
      until explicitly approved.

---

## Deferred until justified

Kubernetes, message queues, service discovery, multi-tenant auth, and
multi-agent orchestration. Each remains out of scope until a milestone proves
it necessary, at which point it gets an ADR.
