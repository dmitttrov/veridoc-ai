# Architecture Decision Records

Lightweight ADRs. Each records context, the decision, and consequences.
Newest last. Status: Accepted unless noted.

---

## ADR-0001 — Monorepo with npm workspaces

**Context.** Four related deployables (web, gateway, AI service, shared
contracts) that must evolve together, on a machine with npm already installed.

**Decision.** Use a single Git repository with **npm workspaces** (`apps/*`,
`packages/*`). The Python service lives in `services/ai` with its own
`pyproject.toml` (not an npm workspace).

**Consequences.** One install, atomic cross-cutting changes, shared contracts by
project reference. No extra monorepo tooling (Nx/Turborepo) — revisit only if
build-graph caching becomes a bottleneck.

---

## ADR-0002 — Two-service split: NestJS gateway + FastAPI AI service

**Context.** ML/inference is idiomatic in Python; the public API and streaming
orchestration are idiomatic in Node/NestJS. Forcing both into one runtime would
compromise one side.

**Decision.** A NestJS **gateway** is the public edge; a FastAPI **AI service**
owns inference and is internal-only.

**Consequences.** Clean language boundaries and independent scaling. Cost: a
network hop and a shared contract to maintain across two languages. This is
**not** microservices — it is the minimum split dictated by the tech stack.

---

## ADR-0003 — Shared contracts via zod, mirrored in Pydantic

**Context.** We want runtime validation at the edge and static types in TS,
plus validated models in Python.

**Decision.** `packages/contracts` defines zod schemas + inferred TS types as
the source of truth. `services/ai/app/models.py` mirrors them in Pydantic v2.
Wire format is camelCase; Python bridges via a camelCase alias generator.

**Consequences.** Strong typing on all three sides. Risk: the TS and Python
definitions can drift; mitigated by keeping them small, co-documented, and
covered by tests that assert the camelCase wire shape (e.g. `tokenCount`).
A future codegen step could remove the hand-mirroring.

---

## ADR-0004 — Server-Sent Events for streaming

**Context.** We need to stream answer tokens from the AI service to the browser
through the gateway.

**Decision.** Use **SSE** (`text/event-stream`) with a JSON-encoded typed event
union. The gateway pipes the upstream SSE bytes straight to the browser.

**Consequences.** Simple, HTTP-native, proxy-friendly, one-directional (all we
need). The browser uses `fetch` + a manual SSE parser (not `EventSource`) so we
can POST a JSON body and attach headers. WebSockets were rejected as
unnecessary bidirectionality.

---

## ADR-0005 — Deterministic mock inference provider for Phase 1

**Context.** The vertical slice must run with no GPU, no model weights, and no
paid APIs, and must be testable in CI.

**Decision.** Ship a `MockProvider` behind an `InferenceProvider` protocol. It
produces deterministic, grounded-style streamed answers with fixture citations
and never invents financial figures. Mock mode is surfaced in health, the
`done` event, and the UI badge.

**Consequences.** Reproducible tests and demos; a clean seam for real providers
(OpenAI-compatible / vLLM) later. The mock is explicitly not representative of
real answer quality and is labelled as such everywhere.

---

## ADR-0006 — Gateway as a transparent SSE proxy (no mid-stream transform)

**Context.** The gateway could parse and re-emit each event, or pipe bytes.

**Decision.** For Phase 1 the gateway **pipes** upstream SSE bytes unchanged,
and only synthesizes a terminal `error` event if opening/transport fails.

**Consequences.** Minimal latency and code. Validation still happens at both
ends (zod on input at the gateway; zod on each event in the browser). If the
gateway later needs to enforce/transform events (e.g. redaction), the parser
already exists on the client side and can be reused server-side.

---

## ADR-0007 — Request validation with zod in controllers (no class-validator)

**Context.** NestJS commonly uses `class-validator` DTOs, but our source of
truth is zod in `packages/contracts`.

**Decision.** Validate request bodies by calling the shared zod schema inside
the controller and throwing `BadRequestException` on failure. Do not install
`class-validator`/`class-transformer` or enable the global `ValidationPipe`.

**Consequences.** One validation definition reused across web and gateway; fewer
dependencies. Cost: we forgo decorator-based DTO ergonomics, which we don't need.

---

## ADR-0008 — PostgreSQL + pgvector as the single retrieval store *(planned)*

**Context.** We will need document metadata, lexical search, and vector search.

**Decision.** Use one PostgreSQL instance with the `pgvector` extension rather
than adding a separate vector database.

**Status.** Proposed (activates Days 2–5). **Consequences.** One system to
operate and back up; SQL joins across metadata and embeddings. Revisit only if
vector workload outgrows a single Postgres.

---

## ADR-0010 — PDF parsing with pypdf, not PyMuPDF (license)

**Context.** Phase 2 needs PDF text extraction. PyMuPDF is powerful and was the
suggested default, but it is licensed **AGPL-3.0** (or a paid commercial
license).

**Decision.** Use **pypdf (BSD-3-Clause)** for validation and text extraction.

**Consequences.** AGPL's network-copyleft is incompatible with this project's
Apache-2.0 licensing and its goal of being freely reusable, so PyMuPDF is
rejected. pypdf is permissive, pure-Python, and dependency-light, and is
sufficient for text-layer extraction with page preservation. Trade-off: pypdf is
less layout/table-aware; if rich layout extraction is later required we will
evaluate other permissive options (e.g. pdfplumber/pdfminer.six, both MIT)
rather than AGPL code. **Status: Accepted.**

## ADR-0011 — Versioned raw-SQL migrations (no ORM/Alembic)

**Context.** We need reproducible schema migrations for Postgres + pgvector.

**Decision.** Forward-only, numbered **raw `.sql`** files applied by a small
idempotent runner (`app/db/migrate.py`) that records applied versions in a
`schema_migrations` table and wraps each file in a transaction.

**Consequences.** Migrations are transparent and review-friendly, and
pgvector-specific DDL (extension, `vector(384)` columns, ivfflat/GIN indexes,
generated `tsvector` columns) is expressed directly. No ORM/Alembic dependency
or autogenerate magic. Trade-off: no automatic diffing or down-migrations; for
this project's forward-only needs that is acceptable. **Status: Accepted.**

## ADR-0012 — asyncpg + raw SQL for data access

**Context.** The AI service is async (FastAPI). We need a Postgres driver with
pgvector support and a permissive license.

**Decision.** Use **asyncpg (Apache-2.0)** with a thin raw-SQL repository layer
and the `pgvector.asyncpg` codec. (psycopg3 was rejected as LGPL-3.0.)

**Consequences.** Permissive licensing, native async, high performance, and
explicit SQL that makes transactions, upserts, and idempotency auditable.
Trade-off: no ORM conveniences; we accept hand-written SQL as a feature here.
**Status: Accepted.**

## ADR-0013 — Idempotent ingestion via content-hash-derived UUIDv5 ids

**Context.** Re-ingesting the same PDF must not create duplicate records.

**Decision.** `documents.id`, `document_pages.id`, and `document_chunks.id` are
deterministic **UUIDv5** values derived from the SHA-256 content hash (plus page
/offset for pages/chunks). `documents.content_hash` is unique. All inserts use
`ON CONFLICT DO NOTHING`, and the pipeline fast-paths an already-stored hash.

**Consequences.** Byte-identical re-ingestion is a no-op that returns the
existing document; chunk identities are stable and reproducible across runs.
Trade-off: two different filenames with identical bytes map to one document —
the correct semantics for deduplication. **Status: Accepted.**

## ADR-0014 — Fixed embedding dimension; pluggable providers; no dimension mixing

**Context.** We want a reproducible default and a real local model, without ever
comparing embeddings from different models/dimensions.

**Decision.** Fix the vector column at `vector(384)`. Ship a **deterministic**
feature-hashing provider (default; reproducible; carries token-overlap signal)
and a real **sentence-transformers/all-MiniLM-L6-v2** provider (Apache-2.0,
384-dim, optional `[embeddings]` extra). Every chunk stores `embedding_model`
and `embedding_dim`; retrieval filters to the active model; the DB rejects
wrong-dimension vectors.

**Consequences.** Tests and the evaluation run with zero heavy dependencies and
are fully reproducible; the real model is a drop-in when wanted. Changing to a
model of a different dimensionality requires a new migration. **Status:
Accepted.**

## ADR-0015 — Hybrid retrieval with Reciprocal Rank Fusion

**Context.** Lexical and semantic retrieval each miss cases the other catches.

**Decision.** Run PostgreSQL full-text search and pgvector cosine search
independently, then fuse with **RRF** (k=60). Retrieval is evidence-only in
Phase 2 (no generation).

**Consequences.** Simple, robust, tunable, and keeps everything in one datastore
(no external vector DB). Cross-encoder reranking is deferred to Phase 3. RRF is
pure and unit-tested; the measured corpus evaluation reports Recall@5 and
MRR@10. **Status: Accepted.**

## ADR-0016 — Exact vector search (no ANN index) at current scale

**Context.** Migration 0001 created an `ivfflat` index for cosine search. On the
small evaluation corpus this produced **non-deterministic, incomplete** results
(approximate search over mostly-empty inverted lists), which broke reproducible
evaluation and surfaced as recall varying run-to-run.

**Decision.** Migration 0002 drops the `ivfflat` index so pgvector performs
**exact** nearest-neighbour search (sequential scan) — deterministic and fully
recalled. A tuned **HNSW** index will be reintroduced when the corpus is large
enough that exact scan is too slow.

**Consequences.** Reproducible, correct retrieval now; O(n) vector scan is fine
at this scale. Reintroducing ANN later is a migration + an eval re-run to quantify
the recall/latency trade. **Status: Accepted.**

## ADR-0017 — Deterministic PDF fixtures (reportlab `invariant=1`)

**Context.** `reportlab` embeds timestamps and a random document id by default,
so building the same fixture PDF twice produced **different bytes** → different
SHA-256 → ingestion created duplicate documents and polluted retrieval.

**Decision.** Build fixtures with `canvas.Canvas(..., invariant=1)`, which emits
byte-identical output for identical input.

**Consequences.** Stable content hashes make ingestion genuinely idempotent and
the evaluation reproducible. **Status: Accepted.**

## ADR-0018 — Cross-encoder reranking (two-stage retrieval)

**Context.** First-stage hybrid retrieval (RRF) orders by cheap signals; a
cross-encoder scoring (query, passage) pairs is more accurate but too costly for
the whole corpus.

**Decision.** Two-stage pipeline: RRF top-N candidates → optional reranker →
top-k. Rerankers are pluggable: `none` (default), `deterministic` (reproducible,
no deps), and `cross-encoder` (`cross-encoder/ms-marco-MiniLM-L-6-v2`,
**Apache-2.0**, CPU-capable, optional `[embeddings]` extra). The reranker score
is kept in a separate field from the RRF `fused` score — the two are never
compared or combined. If a configured real reranker fails to load, the factory
returns `None` (explicit fallback) and responses report `reranked=false`;
reranking is never silently faked.

**Consequences.** Measured on the eval corpus, reranking improves MRR@10 and can
slightly reduce Recall@5 (a real precision/recall trade — see EVALUATION.md).
No hidden downloads in tests/CI (default is `none`/`deterministic`).
**Status: Accepted.**

## ADR-0019 — OpenAI-compatible inference provider; no silent fallback

**Context.** Phase 3 needs real generation without paid APIs and without
exposing an internal model server.

**Decision.** `OpenAICompatibleProvider` talks to a configurable local
OpenAI-compatible server (incl. vLLM) via `/chat/completions`. Config:
`AI_INFERENCE_PROVIDER` (`mock` default | `openai_compatible`),
`AI_INFERENCE_BASE_URL/MODEL/API_KEY/TIMEOUT_S/MAX_TOKENS/TEMPERATURE`. The mock
is the default and the CI backend. On timeout / connection failure / malformed
response / upstream error the provider raises `InferenceError` (buffered path)
or emits a terminal `error` SSE event (streaming path) — it **never** silently
falls back to the mock. Prompts, document content, responses, and API keys are
never logged.

**Consequences.** Real inference is a config change; the internal server stays
private behind the gateway. Integration tests run against an in-process fake
OpenAI server (no network). **Status: Accepted.**

## ADR-0020 — Grounded RAG: evidence markers, citation verification, verify-then-stream

**Context.** Answers about documents must be grounded, must not obey instructions
embedded in documents, and must carry verifiable citations — without
misrepresenting citation validity as factual support.

**Decision.**
- Evidence passages are assembled with short markers (`[E1]`, `[E2]`, …), framed
  explicitly as **untrusted data** the model must never obey.
- The model is told to cite markers and to output a fixed sentinel when evidence
  is insufficient (abstention).
- **Citation verification** maps emitted markers back to retrieved chunks:
  markers that don't map are **fabricated** — stripped from the answer and
  counted (`invalidCitationCount`). Valid citations carry `chunkId` + character
  span, traceable to stored page text.
- **Validity ≠ support**: verification only proves the reference exists; it does
  not check the evidence substantiates the claim. The UI and docs state this.
- **Streaming safety**: the full answer is generated and its citations verified
  **before** any token is streamed to the client (verify-then-stream). This
  trades first-token latency for the guarantee that users never see unverified,
  fabricated-citation content as a final answer.

**Consequences.** Strong grounding/verifiability guarantees at the cost of
first-token latency. Context is bounded (top-k passages, per-passage char cap).
**Status: Accepted.**

## ADR-0021 — Base model: Qwen3-0.6B (pinned revision), LoRA adapter

**Context.** Phase 4 needs a small, permissively licensed instruction model that
fits modest hardware for a controlled, reproducible fine-tuning experiment.

**Decision.** Use `Qwen/Qwen3-0.6B` pinned at revision
`c1899de289a04d12100db370d81485cdf75e47ca` (**Apache-2.0**). Produce a **LoRA**
adapter (PEFT); do not train from scratch and do not redistribute base weights.

**Consequences.** Apache-2.0 permits adapter release with attribution; Qwen3 is
supported by transformers (≥4.51), PEFT, and vLLM; 0.6B fits CPU for smoke/pilot
and small GPUs for real runs. The small size bounds expected quality — this is a
controlled experiment, not a broad-capability claim. **Status: Accepted.**

## ADR-0022 — Extraction task, strict schema, synthetic data, family split

**Context.** We need a fine-tuning task that is useful, measurable, and resistant
to hallucination, with a dataset that can't leak train→test.

**Decision.**
- **Task:** structured extraction of one requested financial metric from
  numbered evidence → strict JSON (`ExtractionResult`, `extra="forbid"`, with a
  supported-vs-abstain invariant enforced by a validator).
- **Grounding:** evidence framed as untrusted data; the model cites an evidence
  marker and must abstain (`supported=false`, nulls) when unsupported; evidence
  markers are validated against the provided set (no invented references).
- **Data:** synthetic, fictional, self-authored (CC0-equivalent); categories =
  answerable, unanswerable/hard-negative, conflicting (restated figures),
  prompt-injection. Deterministic from a seed; deduped; versioned with per-split
  SHA-256.
- **Split:** by `(company, metric)` **family** (hashed), so no template instance
  appears in two splits — prevents leakage. A held-out test set drives both the
  base baseline and the adapter eval with identical decoding.

**Consequences.** Reproducible, leakage-controlled evaluation of a narrow,
verifiable capability. Synthetic data limits external validity (stated in the
model card). **Status: Accepted.**

## ADR-0023 — Training is a separate package; retrieval stays in services/ai

**Context.** Fine-tuning pulls heavy deps (torch/transformers/peft/datasets/
accelerate) that must not bloat the runtime AI service or CI.

**Decision.** Put fine-tuning in a standalone `training/` package with its own
`pyproject.toml` and venv. The trainer core is decoupled from base-model loading
so a no-network CPU smoke test (tiny random Qwen3) exercises the real LoRA/
Trainer/save path. Serving keeps using the OpenAI-compatible provider
(ADR-0019); the adapter is loaded there via a local server, not by importing the
training package.

**Consequences.** The app and its CI stay lean; training deps are opt-in. Real
GPU training/eval are explicit commands, not CI steps. **Status: Accepted.**

## ADR-0024 — Paired bootstrap for base-vs-adapter comparison; GPU inference path

**Context.** Phase 4B compares base and adapter on the *same* held-out
examples. Judging credibility by non-overlapping independent Wilson intervals is
statistically wrong for paired data and overstates significance.

**Decision.** Credibility is decided by a **paired bootstrap** (10k resamples)
over per-example score differences on the shared test set; "credible" means the
95% CI of the mean difference excludes 0. Wilson intervals are still reported for
context but are not the decision rule. Also fixed the eval inference path to
place the model on CUDA and pass an attention mask (both base and adapter use
the identical GPU greedy path).

**Consequences.** Honest, paired significance (schema_valid, value_exact,
metric_exact credible; evidence_ref_valid unchanged). The comparison is only as
meaningful as the (synthetic) test set — see EVALUATION.md. **Status: Accepted.**

## ADR-0025 — Phase 4B executed on the GPU server; synthetic-only claim

**Context.** First real GPU run of the Phase 4 pipeline on a dual RTX PRO 6000
Blackwell server (GPU 0 only; isolated venv bootstrapped without touching system
Python/drivers/services; CUDA-12.8 torch for Blackwell).

**Decision.** Record the measured result as a **controlled proof-of-pipeline on
templated synthetic data** — a credible paired improvement — and explicitly do
**not** claim real-financial-document capability. Server connection details and
all artifacts (data, checkpoints, adapter) stay out of Git; only measured
numbers and code enter the repo.

**Consequences.** Publication remains blocked on a real-document evaluation and
explicit owner approval. **Status: Accepted.**

## ADR-0009 — Fine-tune via LoRA/QLoRA on an open-weight base *(planned)*

**Context.** We want a domain-adapted model without the cost or honesty problems
of claiming from-scratch pretraining.

**Decision.** Use PEFT LoRA/QLoRA on a suitable, license-compatible open-weight
base; serve via vLLM behind the OpenAI-compatible provider.

**Status.** Proposed (activates Days 12–13). **Consequences.** Cheap,
reproducible adaptation with small shippable adapters. See `MODEL_STRATEGY.md`.
