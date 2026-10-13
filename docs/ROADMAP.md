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

## Phase 3 (planned) — Reranking + source-grounded generation

**Goal:** Add a reranker and the first real generation grounded in retrieved
passages.

**Acceptance criteria**
- [ ] Cross-encoder reranker reorders the fused top-k; evaluation shows the
      change vs. the Phase 2 hybrid baseline (honestly reported).
- [ ] `OpenAICompatibleProvider` (local server / vLLM) behind the existing
      provider seam; mock stays the default/CI backend.
- [ ] Grounded-or-abstain prompting with prompt-injection mitigations applied to
      retrieved text (see SECURITY); citations verified against stored spans.

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
