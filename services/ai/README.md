# Veridoc AI Service (FastAPI)

Internal inference service. **Phase 1 ships a deterministic mock provider** — no
GPU, no model weights, no paid APIs. The `InferenceProvider` protocol is the seam
where an OpenAI-compatible backend (e.g. a local vLLM server) plugs in later.

> ⚠️ This service is **internal only**. Do not expose it publicly. The NestJS
> gateway is its sole client.

## Endpoints

| Method | Path                     | Description                                  |
| ------ | ------------------------ | -------------------------------------------- |
| GET    | `/health`                | Liveness + mock-mode flag                    |
| GET    | `/v1/documents`          | Synthetic fixture documents (Phase 1 chat)   |
| POST   | `/v1/chat/stream`        | Streaming mock answer (SSE)                  |
| POST   | `/v1/documents/ingest`   | Ingest an uploaded PDF (multipart)           |
| GET    | `/v1/documents/stored`   | List ingested documents                      |
| POST   | `/v1/retrieve`           | Hybrid retrieval (+rerank) → source passages |
| POST   | `/v1/rag/answer`         | Grounded RAG answer with verified citations (SSE) |

## Phase 2: database, ingestion, retrieval, evaluation

Requires PostgreSQL + pgvector. The easiest way is the Compose `db` service, or
a standalone container:

```bash
docker run -d --name veridoc-db -e POSTGRES_USER=veridoc \
  -e POSTGRES_PASSWORD=veridoc -e POSTGRES_DB=veridoc \
  -p 5432:5432 pgvector/pgvector:pg16
export AI_DATABASE_URL=postgresql://veridoc:veridoc@localhost:5432/veridoc
```

```bash
# Apply migrations (idempotent; also run automatically by the Docker image).
python -m app.db.migrate            # apply pending
python -m app.db.migrate --status   # show applied/pending

# Ingest a local PDF.
python -m app.cli ingest path/to/document.pdf

# Run the reproducible retrieval evaluation (measured Recall@5 / MRR@10).
python -m app.eval.run              # deterministic embeddings (default)
AI_EMBEDDING_PROVIDER=sentence-transformers python -m app.eval.run  # real model
```

### Embeddings

- `AI_EMBEDDING_PROVIDER=deterministic` (default): reproducible feature-hashing,
  no heavy deps. Used by tests and CI.
- `AI_EMBEDDING_PROVIDER=sentence-transformers`: real local model
  (`all-MiniLM-L6-v2`, Apache-2.0). Install the extra:
  `pip install -e ".[dev,embeddings]"`.

Both are 384-dim; the DB rejects any other dimension (no silent mixing).

### Database integration tests

DB-backed tests are skipped unless a test database is configured:

```bash
VERIDOC_TEST_DATABASE_URL=postgresql://veridoc:veridoc@localhost:5432/veridoc pytest
```

## Local development

```bash
cd services/ai
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run the service
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Quality gates
pytest
ruff check .
mypy app
```

## Configuration

See [`.env.example`](./.env.example). All variables are prefixed `AI_`.
