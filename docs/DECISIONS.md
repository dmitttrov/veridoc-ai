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

## ADR-0009 — Fine-tune via LoRA/QLoRA on an open-weight base *(planned)*

**Context.** We want a domain-adapted model without the cost or honesty problems
of claiming from-scratch pretraining.

**Decision.** Use PEFT LoRA/QLoRA on a suitable, license-compatible open-weight
base; serve via vLLM behind the OpenAI-compatible provider.

**Status.** Proposed (activates Days 12–13). **Consequences.** Cheap,
reproducible adaptation with small shippable adapters. See `MODEL_STRATEGY.md`.
