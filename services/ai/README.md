# Veridoc AI Service (FastAPI)

Internal inference service. **Phase 1 ships a deterministic mock provider** — no
GPU, no model weights, no paid APIs. The `InferenceProvider` protocol is the seam
where an OpenAI-compatible backend (e.g. a local vLLM server) plugs in later.

> ⚠️ This service is **internal only**. Do not expose it publicly. The NestJS
> gateway is its sole client.

## Endpoints

| Method | Path                | Description                              |
| ------ | ------------------- | ---------------------------------------- |
| GET    | `/health`           | Liveness + mock-mode flag                |
| GET    | `/v1/documents`     | Synthetic fixture documents              |
| POST   | `/v1/chat/stream`   | Streaming grounded answer (SSE)          |

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
