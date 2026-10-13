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

## Days 2–3 — Document ingestion foundation

**Goal:** Replace fixtures with real (publicly shareable, synthetic or public)
documents, parsed with page-level provenance, stored in PostgreSQL + pgvector.

**Acceptance criteria**
- [ ] `docker compose` adds a Postgres+pgvector service with a migration that
      creates `documents`, `pages`, and `chunks` tables.
- [ ] An ingestion CLI in `services/ai` parses a PDF into pages → chunks with
      `(document_id, page, char_span)` provenance; fixtures remain synthetic.
- [ ] Upload endpoint on the gateway enforces type/size limits (see SECURITY).
- [ ] Tests: parser produces stable chunk spans; ingestion is idempotent.

---

## Days 4–5 — Retrieval (lexical + vector)

**Goal:** Retrieve candidate passages for a question.

**Acceptance criteria**
- [ ] Embedding step (local/open model) populates `chunks.embedding` (pgvector).
- [ ] Vector similarity search and Postgres full-text search both implemented.
- [ ] `/v1/chat/stream` uses retrieval to attach **real** citations (still mock
      generation) limited to selected documents.
- [ ] Tests: known query retrieves the known passage above a ranking threshold.

---

## Days 6–7 — Hybrid retrieval + reranking

**Goal:** Measurably better retrieval than either single strategy.

**Acceptance criteria**
- [ ] Hybrid fusion (e.g. reciprocal rank fusion) of lexical + vector results.
- [ ] A cross-encoder reranker reorders the fused top-k.
- [ ] A small, committed evaluation set (synthetic Q→passage pairs) with a
      retrieval metric (e.g. recall@k, MRR); hybrid ≥ each baseline.
- [ ] No fabricated numbers — metrics are computed by a committed script.

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
