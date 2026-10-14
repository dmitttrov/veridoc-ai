# Veridoc AI

> Source-grounded financial document intelligence. Ask natural-language
> questions about publicly shareable financial documents and get answers tied to
> their source passages, with document and page citations.

**Status: experimental.** A full RAG system (ingestion → hybrid retrieval +
reranking → grounded, citation-verified generation) plus a reproducible **LoRA
fine-tuning + evaluation** pipeline for a small financial-fact **extraction**
adapter over `Qwen/Qwen3-0.6B`. Runs locally with no paid services.

This is a public, open-source **portfolio** project. See
[`docs/NORTH_STAR.md`](docs/NORTH_STAR.md).

> ## ⚠️ Experimental model — read before using
>
> - The adapter is **fine-tuned (LoRA), NOT trained from scratch**, over a
>   pinned open-weight base (`Qwen/Qwen3-0.6B`, Apache-2.0). We publish the
>   **adapter only**, never base weights.
> - Evaluation evidence is **templated prose containing real SEC XBRL figures**
>   — **not** verbatim filing excerpts.
> - The frozen 239-example SEC benchmark was first used to find adapter-**v1**
>   weaknesses, which were then **specifically targeted in v2 training**. So for
>   v2 that benchmark is a **targeted regression check** — its near-perfect
>   (≈100%) scores are **NOT independent generalization results**.
> - **Authentic filing-text generalization remains untested** (real 10-K/10-Q
>   prose, tables, footnotes).
> - This model is **experimental** and **not suitable for financial advice or
>   unsupervised high-stakes decisions**. Always verify against primary sources.
>
> Full methodology and measured numbers: [`docs/EVALUATION.md`](docs/EVALUATION.md)
> and the model card [`training/MODEL_CARD.md`](training/MODEL_CARD.md).

## Architecture

```
  Browser (React/TS, Vite)  ──SSE──►  NestJS gateway (public edge: zod, timeouts)
        │  upload / ask                        │  server-to-server (internal only)
        ▼                                      ▼
  Grounded Answer / Retrieval UI      FastAPI AI service
                                        • PDF ingest (pypdf): normalize → chunk → embed
                                        • Hybrid retrieval: Postgres FTS + pgvector + RRF
                                        • Optional cross-encoder reranker
                                        • Grounded gen: evidence(untrusted)→LLM→verify citations
                                        • Provider: mock (default) | OpenAI-compatible / vLLM
                                        │                         │
                                        ▼                         ▼
                              PostgreSQL + pgvector     LoRA adapter (Qwen3-0.6B) [training/]
```

Full details + trade-offs: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## What works today

- **Fine-tuning pipeline (Phase 4):** a standalone `training/` package with a
  reproducible synthetic dataset, a strict Pydantic extraction schema, **LoRA**
  SFT over a pinned `Qwen/Qwen3-0.6B` base, and base-vs-adapter evaluation (with
  a no-network CPU smoke test). Produces a **LoRA adapter** (not fine-tuned from
  scratch; nothing published). Draft model card + release checklist included.
- **Grounded answers (Phase 3):** ask a question and get a language-model answer
  **grounded in retrieved evidence** with **verified citations** — fabricated
  citation references are detected and removed, the model is instructed to ignore
  instructions embedded in documents, and the answer is only streamed after
  citations are verified. The model is **not fine-tuned**; the default provider
  is a deterministic mock (real local/vLLM inference is a config change).
- **Hybrid retrieval + reranking (Phase 2/3):** upload a PDF → validated,
  normalized, chunked, embedded, stored in PostgreSQL + pgvector; hybrid search
  (FTS + exact vector + RRF) with optional cross-encoder reranking returns source
  passages with exact text, page, span, scores, and a traceable citation.
  Re-ingesting the same PDF is idempotent.
- **Mock chat (Phase 1):** a React streaming chat over SSE, still available via
  the view switcher.
- A NestJS gateway (public edge) that validates requests, enforces upload
  limits, and streams/forwards to the internal FastAPI AI service.
- Pluggable embeddings: deterministic (default, reproducible) and a real local
  `sentence-transformers` model.
- Shared, runtime-validated contracts (`@veridoc/contracts`).
- A reproducible retrieval evaluation (`python -m app.eval.run`) — measured
  results in [`docs/EVALUATION.md`](docs/EVALUATION.md).
- Health endpoints, automated tests, lint/type checks, and CI (incl. DB-backed
  integration tests against pgvector).

## Repository layout

```
veridoc-ai/
├── apps/
│   ├── web/              React + TypeScript + Vite client
│   └── api/              NestJS API gateway (public edge)
├── services/
│   └── ai/               FastAPI inference service (internal; mock provider)
├── packages/
│   └── contracts/        Shared TypeScript types + zod schemas
├── training/             Phase 4: LoRA fine-tuning + evaluation (standalone)
├── infra/                Docker Compose + Dockerfiles (web, api, ai, db)
├── docs/                 North Star, Architecture, Roadmap, Decisions,
│                         Security, Model Strategy
└── .github/workflows/    CI (lint, type-check, test, build)
```

## Prerequisites

- Node.js ≥ 20 and npm
- Python 3.11
- (Optional) Docker, to run the whole stack with one command

## Quick start — Docker (whole stack)

```bash
docker compose -f infra/docker-compose.yml up --build
# open http://localhost:5173
```

This starts PostgreSQL + pgvector (`db`), the AI service (`ai`, which runs
database migrations on startup), the gateway (`api`), and the web app (`web`).
The AI service and database are intentionally **not** published to the host (see
[`docs/SECURITY.md`](docs/SECURITY.md)).

To ingest a PDF and query it from the command line instead:

```bash
curl -F "file=@yourdoc.pdf;type=application/pdf" http://localhost:3000/api/documents/upload
curl -X POST http://localhost:3000/api/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"What was total revenue?","topK":5}'
```

## Quick start — run services directly

Open three terminals from the repository root.

**1) AI service (FastAPI)**

```bash
cd services/ai
python -m venv .venv
. .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**2) API gateway (NestJS)**

```bash
npm install
npm run build:contracts         # build shared contracts once
cp apps/api/.env.example apps/api/.env   # optional; defaults work
npm run dev:api                 # http://localhost:3000
```

**3) Web client (React/Vite)**

```bash
cp apps/web/.env.example apps/web/.env.local   # optional; defaults work
npm run dev:web                 # http://localhost:5173
```

Open <http://localhost:5173>, (optionally) select documents, and ask a question
such as *"What was total revenue for FY2023?"* — the mock answer streams in with
citations, and the **MOCK MODE** badge is shown.

### Verify the pipeline from the command line

```bash
# Gateway health
curl http://localhost:3000/health

# Stream a mock answer end-to-end (gateway -> AI service -> back)
curl -N -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What was total revenue for FY2023?","documentIds":["doc-acme-fy2023"]}'
```

## Testing & quality gates

```bash
# JavaScript/TypeScript (from repo root)
npm run build:contracts
npm run lint
npm run typecheck
npm run test

# Python AI service
cd services/ai
pytest
ruff check .
mypy app
```

CI runs all of the above on every push/PR (`.github/workflows/ci.yml`).

## Configuration

No secrets are committed. Each service documents its environment variables in a
`.env.example`:

- `apps/api/.env.example` — gateway port, AI service URL, CORS origin, timeouts.
- `apps/web/.env.example` — gateway base URL for the browser.
- `services/ai/.env.example` — provider selection and model name.

## Documentation

- [North Star](docs/NORTH_STAR.md) — mission, users, scope.
- [Architecture](docs/ARCHITECTURE.md) — components, flows, trade-offs.
- [Roadmap](docs/ROADMAP.md) — 14-day plan with acceptance criteria.
- [Decisions](docs/DECISIONS.md) — architecture decision records.
- [Security](docs/SECURITY.md) — trust boundaries, uploads, prompt injection.
- [Model Strategy](docs/MODEL_STRATEGY.md) — base models, LoRA/QLoRA, evaluation.
- [Evaluation](docs/EVALUATION.md) — measured retrieval + base/v1/v2 extraction.
- [Model Card](training/MODEL_CARD.md) — the LoRA adapter (experimental).
- [Attributions](docs/ATTRIBUTIONS.md) — third-party licenses & audit.
- [Contributing](CONTRIBUTING.md).

## Demo

No hosted demo (nothing is deployed). To try it locally:

- **Full RAG app:** `docker compose -f infra/docker-compose.yml up --build`, then
  open <http://localhost:5173> — upload a PDF, retrieve evidence, and (mock or
  real inference) get a citation-verified grounded answer. See
  [`infra/README.md`](infra/README.md).
- **The extraction adapter:** load `Qwen/Qwen3-0.6B` + the LoRA adapter and run a
  structured extraction — see the loading example in
  [`training/MODEL_CARD.md`](training/MODEL_CARD.md) and commands in
  [`training/README.md`](training/README.md).

## License

Apache-2.0 (see [`LICENSE`](LICENSE) and [`docs/ATTRIBUTIONS.md`](docs/ATTRIBUTIONS.md)).
The published Hugging Face artifact is an **adapter only**; the Qwen3-0.6B base
(Apache-2.0) is downloaded from its original source, not redistributed here.
