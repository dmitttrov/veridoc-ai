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

## ADR-0009 — Fine-tune via LoRA/QLoRA on an open-weight base *(planned)*

**Context.** We want a domain-adapted model without the cost or honesty problems
of claiming from-scratch pretraining.

**Decision.** Use PEFT LoRA/QLoRA on a suitable, license-compatible open-weight
base; serve via vLLM behind the OpenAI-compatible provider.

**Status.** Proposed (activates Days 12–13). **Consequences.** Cheap,
reproducible adaptation with small shippable adapters. See `MODEL_STRATEGY.md`.
