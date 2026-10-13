# Infrastructure (local development)

Phase 1 ships a minimal Docker Compose stack: **web**, **api**, **ai**. No GPU,
no paid services, no database yet (PostgreSQL + pgvector arrives with ingestion
— see `docs/ROADMAP.md`).

## Run the stack

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Then open <http://localhost:5173>.

| Service | Host port | Notes |
| ------- | --------- | ----- |
| web     | 5173 → 80 | Static React app served by nginx |
| api     | 3000      | NestJS gateway (the public edge)  |
| ai      | *(none)*  | **Internal only** — intentionally not published |

The AI service has no published host port: it is reachable only by the gateway
on the internal `veridoc` network. See `docs/SECURITY.md`.

## Configuration

- The web image bakes in `VITE_API_BASE_URL` (build arg, defaults to
  `http://localhost:3000`) because it is called from the browser.
- The gateway reads `AI_SERVICE_URL=http://ai:8000` to reach the AI service over
  the compose network.

## Tear down

```bash
docker compose -f infra/docker-compose.yml down
```
