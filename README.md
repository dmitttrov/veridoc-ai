# Veridoc AI

> Source-grounded financial document intelligence. Ask natural-language
> questions about publicly shareable financial documents and get answers tied to
> their source passages, with document and page citations.

**Status: Phase 1 — vertical slice.** The system runs end-to-end
(React → NestJS → FastAPI) with a **deterministic mock** inference provider.
No GPU, no model weights, and no paid services are required. Mock mode is
clearly labelled in the UI and in every response.

This is a public, open-source portfolio project. It is **not** financial advice,
and it handles only publicly shareable, non-sensitive documents. See
[`docs/NORTH_STAR.md`](docs/NORTH_STAR.md).

## What works today

- A React UI with a document list, a streaming chat, and inline citations.
- A NestJS gateway that validates requests and streams answers over SSE.
- A FastAPI AI service with a pluggable `InferenceProvider` and a deterministic
  mock backend that produces grounded-style answers with fixture citations.
- Shared, runtime-validated contracts (`@veridoc/contracts`).
- Health endpoints, automated tests, lint/type checks, and CI.

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

The AI service is intentionally **not** published to the host (see
[`docs/SECURITY.md`](docs/SECURITY.md)).

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

## License

Apache-2.0.
