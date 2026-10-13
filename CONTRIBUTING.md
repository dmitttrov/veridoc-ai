# Contributing to Veridoc AI

Thanks for your interest. Veridoc AI is a portfolio/reference project with a
strong emphasis on **correctness, reproducibility, and honest measurement**.

## Ground rules

- **Never fabricate metrics.** Every number in the docs is produced by a
  committed, re-runnable script. If you can't measure it, don't claim it.
- **No secrets, private data, or model weights in Git.** `data/`, `artifacts/`,
  `*.safetensors`, and `.env` are git-ignored; keep it that way. Set
  `SEC_USER_AGENT` to your own contact — never hardcode personal emails.
- **Strict typing & lint** everywhere (TypeScript strict, Python ruff + mypy).
- **Don't present templated/XBRL-derived evidence as authentic filing text.**

## Repository layout

| Path | What | Toolchain |
| --- | --- | --- |
| `apps/web` | React + TypeScript + Vite UI | Node 20, Vitest |
| `apps/api` | NestJS API gateway (public edge) | Node 20, Jest |
| `services/ai` | FastAPI AI service (RAG, retrieval, mock/real inference) | Python 3.11, pytest/ruff/mypy |
| `packages/contracts` | Shared zod contracts | Node 20, Vitest |
| `training` | LoRA fine-tuning + evaluation (standalone) | Python 3.11+, pytest/ruff/mypy |
| `infra` | Docker Compose + Dockerfiles | Docker |
| `docs` | North Star, Architecture, Decisions, Security, Evaluation, Model Strategy, Attributions |

## Local setup

```bash
# JS workspaces
npm install && npm run build:contracts

# AI service
cd services/ai && python -m venv .venv && . .venv/Scripts/activate
pip install -e ".[dev]"

# Training (separate env; CUDA torch for GPU, see training/README.md)
cd training && python -m venv .venv && . .venv/Scripts/activate && pip install -e ".[dev]"
```

## Quality gates (must pass before a PR)

```bash
# JS
npm run lint && npm run typecheck && npm run test
# AI service (DB-backed tests need a pgvector instance; otherwise they skip)
cd services/ai && ruff check . && mypy app && pytest
# Training
cd training && ruff check . && mypy veridoc_ft && pytest
```

CI (`.github/workflows/ci.yml`) runs lint, type-check, tests, and builds, plus a
DB-backed integration pass against pgvector.

## Pull requests

- Keep changes focused; match the surrounding style.
- Add/update tests for real behavior (not coverage theater).
- Update the relevant `docs/*` and any ADR in `docs/DECISIONS.md` when you change
  architecture or make a notable trade-off.
- Describe what you measured and how.

## Reporting security issues

See [`docs/SECURITY.md`](docs/SECURITY.md). Please open a minimal,
reproduction-focused issue (or private report) rather than posting exploit
details publicly.
