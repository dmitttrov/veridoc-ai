# Veridoc AI

> Source-grounded financial document intelligence. Ask natural-language
> questions about publicly shareable financial documents and get answers tied to
> their source passages, with document and page citations.

**Status: Phase 2 — ingestion + hybrid retrieval.** Real PDFs can be uploaded,
parsed, chunked, embedded locally, and searched with hybrid retrieval returning
**source passages with verifiable page-level citations**. Generation is still a
**deterministic mock** (clearly labelled); the retrieval UI shows evidence, not
AI-authored answers. No GPU and no paid services are required.

This is a public, open-source portfolio project. It is **not** financial advice,
and it handles only publicly shareable, non-sensitive documents. See
[`docs/NORTH_STAR.md`](docs/NORTH_STAR.md).

## What works today

- **Document retrieval (Phase 2):** upload a PDF → it is validated, normalized,
  chunked, embedded, and stored in PostgreSQL + pgvector; ask a question and get
  hybrid-retrieved source passages (FTS + vector + RRF) with exact text, page,
  character span, scores, and a traceable citation. Re-ingesting the same PDF is
  idempotent.
- **Mock chat (Phase 1):** a React streaming chat over SSE with a deterministic
  mock provider and inline citations, still available via the view switcher.
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
├── infra/                Docker Compose + Dockerfiles (web, api, ai)
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
- [Evaluation](docs/EVALUATION.md) — measured retrieval Recall@5 / MRR@10.

## License

Apache-2.0.
