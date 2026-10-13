# Veridoc AI — Architecture

This document describes the system as it exists after **Phase 3 (reranking +
grounded generation)** and the seams designed in for later phases. Work built
now and future work are labelled throughout.

## Phase 3 additions (reranking + real inference + grounded RAG)

Phase 3 adds a trustworthy answer path on top of Phase 2 retrieval:

- **Cross-encoder reranking** (optional, pluggable): RRF top-N → reranker →
  top-k. Providers: `none` (default), `deterministic` (reproducible, no deps),
  `cross-encoder` (`ms-marco-MiniLM-L-6-v2`, Apache-2.0). Reranker scores are
  kept separate from RRF scores; an unavailable real reranker falls back
  explicitly (`reranked=false`), never silently.
- **Real inference** via `OpenAICompatibleProvider` behind the existing
  `InferenceProvider` seam — targets a local OpenAI-compatible server (incl.
  vLLM). The mock stays the default and CI backend; the provider never silently
  falls back to the mock.
- **Grounded RAG** (`POST /v1/rag/answer` → gateway `POST /api/rag`):
  question → hybrid retrieval (+optional rerank) → evidence assembly (passages
  framed as untrusted data with `[E1]…` markers) → LLM → **citation
  verification** → **verify-then-stream** of the validated answer (SSE).

RAG data flow:

```
browser → POST /api/rag (gateway: validate)
        → POST /v1/rag/answer (AI service)
             → retrieve (+rerank)  → assemble evidence ([E1]… markers, untrusted-data framing)
             → provider.generate() [BUFFERED]   (mock | openai_compatible)
             → verify citations: markers → retrieved chunks; fabricated → stripped+counted
             → stream the VERIFIED answer token-by-token, then a citations event, then done
```

Key safety properties: retrieved text is never executed and is marked untrusted;
the model is instructed to ignore instructions inside evidence; citation
*validity* (marker→chunk) is verified and is explicitly **not** the same as
citation *support*; nothing is streamed until verification completes.

---

## Phase 2 additions (ingestion + hybrid retrieval)

Phase 2 makes Veridoc ingest real PDFs and retrieve real evidence with
page-level provenance. **Generation is still not implemented** — the retrieval
UI shows source passages (evidence), explicitly *not* AI-authored answers.

- **PostgreSQL + pgvector** store documents, pages, chunks, and ingestion runs.
- **Secure PDF ingestion** (pypdf): validate → extract → deterministic
  normalize → deterministic chunk → embed → store, transactionally and
  idempotently (deterministic UUIDv5 ids keyed on the SHA-256 content hash).
- **Pluggable embeddings**: a deterministic feature-hashing provider (default,
  no heavy deps, reproducible) and a real local `sentence-transformers`
  provider (`all-MiniLM-L6-v2`, 384-dim, Apache-2.0).
- **Hybrid retrieval**: PostgreSQL full-text search + pgvector cosine
  similarity, fused with Reciprocal Rank Fusion; results carry exact text,
  page, character span, per-leg scores, and a traceable citation.
- **Gateway upload** endpoint (multipart) forwarding to the internal AI service;
  **retrieval** endpoint returning typed passages.

New data flow (ingestion): browser → `POST /api/documents/upload` (gateway,
size/type checks) → `POST /v1/documents/ingest` (AI service) → validate/extract/
normalize/chunk/embed → single transaction writing `documents`, `document_pages`,
`document_chunks`; the attempt is recorded in `ingestion_runs`.

New data flow (retrieval): browser → `POST /api/retrieve` → `POST /v1/retrieve`
→ lexical + vector legs over `document_chunks` (filtered to the active embedding
model) → RRF fusion → passages whose `text` is exactly
`document_pages.normalized_text[char_start:char_end]`.

---

This document describes the system as it exists after **Phase 1 (vertical
slice)** and the seams designed in for later phases. MVP (built now) and future
work are labelled throughout.

## 1. Component overview

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                        Browser                              │
                 │   apps/web — React + TypeScript + Vite                      │
                 │   • Document list • Streaming chat • Citations panel        │
                 └───────────────▲───────────────────────────┬───────────────┘
                                 │ HTTPS/SSE (text/event-stream)
                                 │ (CORS-restricted to the web origin)
                 ┌───────────────┴───────────────────────────▼───────────────┐
                 │        apps/api — NestJS API gateway (public edge)          │
                 │  • Validates requests with shared zod contracts             │
                 │  • Orchestration + timeouts + error shaping                 │
                 │  • Re-streams SSE from the AI service to the browser        │
                 └───────────────▲───────────────────────────┬───────────────┘
                                 │ Private network only (never public)
                                 │ JSON request / SSE response
                 ┌───────────────┴───────────────────────────▼───────────────┐
                 │     services/ai — FastAPI inference service (internal)      │
                 │  • Pydantic models mirroring the contracts                  │
                 │  • InferenceProvider abstraction                            │
                 │  • MockProvider (deterministic)  [MVP]                      │
                 │  • OpenAI-compatible / vLLM provider          [future]      │
                 │  • Retrieval + reranking                      [future]      │
                 └───────────────▲───────────────────────────┬───────────────┘
                                 │                            │
                      [future]   │ pgvector queries           │ [future] model server
                 ┌───────────────┴──────────────┐   ┌─────────▼───────────────┐
                 │ PostgreSQL + pgvector         │   │ vLLM (OpenAI-compatible)│
                 │ documents, chunks, embeddings │   │ domain-adapted LoRA     │
                 └───────────────────────────────┘   └─────────────────────────┘

packages/contracts — shared TypeScript types + zod schemas (single source of truth)
```

## 2. Responsibilities

### apps/web (React) — MVP
- Renders the document list, the conversation, and inline citations.
- Submits chat requests and consumes the SSE stream, appending token deltas to
  the active assistant turn.
- Surfaces **MOCK MODE** prominently until a real model is confirmed active.
- Talks **only** to the gateway; it never has the AI service URL.

### apps/api (NestJS) — MVP
- The single public entry point ("edge"). Owns CORS, request validation,
  timeouts, and error shaping.
- Validates the request body against `ChatRequestSchema` (zod) and rejects
  malformed input with HTTP 400 before any upstream call.
- Opens the upstream SSE stream from the AI service and pipes bytes straight
  through to the browser (transparent proxy — low overhead, preserves the
  typed event contract end-to-end).
- Converts upstream/transport failures into a terminal `error` SSE event so the
  client always sees a well-formed stream.

### services/ai (FastAPI) — MVP + future
- Owns inference. Exposes `/health`, `/v1/documents`, `/v1/chat/stream`.
- `InferenceProvider` protocol decouples the API surface from the backend:
  - **MVP:** `MockProvider` — deterministic, grounded-style streamed answers
    with fixture citations. No GPU, no model, no network.
  - **Future:** an OpenAI-compatible provider pointing at a local **vLLM**
    server hosting the domain-adapted model; plus retrieval + reranking.
- This service is **internal-only** and must never be published to the host or
  the internet.

### packages/contracts — MVP
- The single source of truth for wire types: `ChatRequest`, `ChatStreamEvent`
  (discriminated union: `token` | `citations` | `done` | `error`),
  `DocumentSummary`, `Citation`, `HealthStatus`.
- TypeScript consumers import the zod schemas (runtime validation) and inferred
  types (compile-time safety). The Python service mirrors them in Pydantic
  (`services/ai/app/models.py`), with a camelCase wire format bridged by an
  alias generator. A change in one must be mirrored in the other.

## 3. Request / data flow — chat (MVP)

1. User types a question; the web client POSTs `ChatRequest` JSON to
   `POST /api/chat` on the gateway, with `Accept: text/event-stream`.
2. The gateway validates the body with zod. Invalid → `400` and stop.
3. The gateway opens `POST /v1/chat/stream` on the AI service with an
   `AbortController` wired to both a connect timeout and the client connection.
4. The AI service selects the configured provider. The `MockProvider` composes
   a deterministic answer, tokenizes it, and yields `token` events, then a
   `citations` event, then a terminal `done` event.
5. Each event is serialized as an SSE record (`data: {json}\n\n`) and streamed
   to the gateway, which writes the bytes straight to the browser response.
6. The web client parses the SSE stream (handling chunk-split records),
   validates each event against the contract, and updates the UI: token deltas
   append to the answer, citations render beneath it, `done` reveals mock mode.
7. If the client disconnects, the gateway aborts the upstream request, which the
   AI service detects (`request.is_disconnected()`) and stops generating.

## 4. Technology choices and trade-offs

| Area | Choice | Why | Trade-off / alternative |
| --- | --- | --- | --- |
| Monorepo | npm workspaces | Built into npm (already present), zero extra tooling | Less powerful than Nx/Turborepo; fine at this size |
| Gateway | NestJS | Structured DI, testable controllers, first-class SSE/streaming | Heavier than bare Express; justified by growth path |
| AI service | FastAPI + Pydantic v2 | Idiomatic Python AI stack, async streaming, strict models | Separate runtime from the gateway; the split is deliberate (Python owns ML) |
| Contracts | zod + inferred types; mirrored Pydantic | Runtime validation at the edge + static safety | Two definitions kept in sync by hand; documented and test-guarded |
| Streaming | Server-Sent Events | One-way token streaming, trivial over HTTP, proxy-friendly | No bidirectional channel (don't need one); WebSocket would be overkill |
| Gateway→AI | Transparent SSE pipe | Minimal latency/overhead, preserves typed events | Gateway doesn't transform events (acceptable; validation lives at both ends) |
| Mock provider | Deterministic templated output | Reproducible tests + demo with no GPU/model/cost | Not representative of real model quality (clearly labelled) |
| Retrieval store | PostgreSQL + pgvector **(built, Phase 2)** | One store for metadata + lexical + vector; operationally simple | A dedicated vector DB would add ops surface without clear benefit at this scale |
| PDF parser | pypdf (BSD-3) **(built, Phase 2)** | Permissive license, pure-Python, no system deps | Less layout-aware than PyMuPDF — but PyMuPDF is AGPL (see ADR-0010) |
| DB driver | asyncpg (Apache-2.0) **(built, Phase 2)** | Permissive, async, fast; pgvector codec support | No ORM — raw SQL by choice (ADR-0012) |
| Embeddings | deterministic + all-MiniLM-L6-v2 **(built, Phase 2)** | Reproducible default; real model is small/Apache-2.0/CPU-ok | Hashing provider is not semantic; real model is behind an optional extra |
| Retrieval | FTS + pgvector (exact) + RRF **(built, Phase 2)** | Hybrid beats either leg; RRF simple/robust; exact search is deterministic at this scale | ANN (HNSW) deferred until the corpus needs it (ADR-0016) |
| Reranking | ms-marco-MiniLM-L-6-v2 (Apache-2.0) **(built, Phase 3)** | More accurate top ranking; CPU-capable; optional | Improves MRR but can trade Recall@5; pluggable + deterministic fallback |
| Generation | OpenAI-compatible provider (vLLM-ready) **(built, Phase 3)** | Local, no paid API; mock default; no silent fallback | GPU needed for a real model; isolated behind the provider seam |

## 5. Cross-cutting concerns

- **Configuration:** environment variables only, validated at startup
  (zod in the gateway, `pydantic-settings` in the AI service). No secrets in
  code. `.env.example` documents every knob.
- **Error handling & timeouts:** the gateway applies an upstream connect
  timeout and propagates client disconnects via `AbortController`. Recoverable
  inference failures are delivered as terminal `error` events, not dropped
  connections.
- **Observability:** structured logs in both services today. OpenTelemetry
  tracing across the gateway → AI hop is planned (see ROADMAP) and kept in mind
  by threading a single request through clear boundaries.
- **Testing:** unit/contract tests per package (vitest, Jest, pytest) plus an
  end-to-end smoke path exercised during development (documented in the README).

## 6. What is intentionally NOT here

No Kubernetes, message broker, service discovery, or multi-agent framework.
The two-service split (gateway + AI) is the minimum needed to keep ML concerns
in Python behind a typed public edge. Additional infrastructure will be added
only when a concrete need is demonstrated and recorded in `DECISIONS.md`.
