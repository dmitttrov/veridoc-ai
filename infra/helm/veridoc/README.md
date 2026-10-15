# Veridoc AI — Helm chart

Deploys the full Veridoc AI stack to Kubernetes: the web SPA, the NestJS API
gateway, and the FastAPI AI service, with an **optional bundled PostgreSQL +
pgvector** database for demo/dev.

- Chart: `infra/helm/veridoc`
- Images: `ghcr.io/<owner>/veridoc-{api,ai,web}` (published by
  `.github/workflows/release.yml`)
- Requires: Kubernetes ≥ 1.23, Helm ≥ 3.8

## Quick start (demo — bundled Postgres)

```bash
helm install veridoc infra/helm/veridoc \
  --namespace veridoc --create-namespace \
  --set image.owner=dmitttrov \
  --set image.tag=edge
```

Then port-forward the web service (no ingress by default):

```bash
kubectl -n veridoc port-forward svc/veridoc-web 8080:80
# open http://localhost:8080
```

For a self-contained local demo you'll also want the browser to reach the
gateway. The simplest path is to enable the ingress (below) so the SPA can use
its default same-origin `/api` routing.

## Typical demo with ingress

```bash
helm install veridoc infra/helm/veridoc \
  -n veridoc --create-namespace \
  --set image.owner=dmitttrov --set image.tag=edge \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.host=veridoc.local \
  --set webOrigin=http://veridoc.local
```

The ingress routes `/api` → gateway and `/` → web on one host, so the SPA's
default same-origin `apiBaseUrl` ("") works. `webOrigin` must match the
browser-facing host or the gateway's CORS will reject requests.

## Production (external managed Postgres + TLS + autoscaling)

pgvector is required. Use a managed Postgres that supports it (e.g. RDS with the
`vector` extension, CloudSQL, Supabase), then:

```bash
helm install veridoc infra/helm/veridoc \
  -n veridoc --create-namespace \
  --set image.owner=dmitttrov --set image.tag=1.0.0 \
  --set postgresql.enabled=false \
  --set externalDatabase.existingSecret=veridoc-db \
  --set externalDatabase.existingSecretKey=url \
  --set ingress.enabled=true --set ingress.className=nginx \
  --set ingress.host=veridoc.example.com \
  --set ingress.tls.enabled=true --set ingress.tls.secretName=veridoc-tls \
  --set webOrigin=https://veridoc.example.com \
  --set api.autoscaling.enabled=true \
  --set ai.autoscaling.enabled=true \
  --set networkPolicy.enabled=true \
  --set podDisruptionBudget.enabled=true
```

Create the DB secret first (value is a full connection string):

```bash
kubectl -n veridoc create secret generic veridoc-db \
  --from-literal=url='postgresql://user:pass@db.internal:5432/veridoc'
```

## Key values

| Key | Default | Purpose |
|-----|---------|---------|
| `image.owner` | `dmitttrov` | GHCR owner (set to yours) |
| `image.tag` | `.Chart.AppVersion` | image tag; use `edge` or a `sha-`/semver tag |
| `webOrigin` | `http://localhost` | CORS allow-origin; must match browser URL |
| `web.apiBaseUrl` | `""` (same-origin) | absolute gateway URL if web and api are on different hosts |
| `migrations.strategy` | `init` | `init` (initContainer) \| `hook` (Helm Job, external DB only) \| `none` |
| `postgresql.enabled` | `true` | bundled pgvector StatefulSet (demo) vs external DB |
| `externalDatabase.url` / `.existingSecret` | `""` | used when `postgresql.enabled=false` |
| `secrets.inferenceApiKey` / `.existingSecret` | `""` | API key for the OpenAI-compatible inference provider |
| `ingress.*`, `*.autoscaling.*`, `networkPolicy.enabled`, `podDisruptionBudget.enabled` | off | production toggles |

See `values.yaml` for the full set (resources, probes, security contexts, etc.).

## Validate without a cluster

```bash
helm lint infra/helm/veridoc
helm template veridoc infra/helm/veridoc            # bundled-Postgres defaults
helm template veridoc infra/helm/veridoc \
  --set postgresql.enabled=false \
  --set externalDatabase.url=postgresql://u:p@h:5432/d
```

CI runs these on every push (the `Helm chart (lint + template)` job).

## Notes & caveats

- **Bundled Postgres is demo-grade** — no backups; losing the PVC loses all data.
  Production should use an external managed database.
- If you set `postgresql.auth.password` explicitly, avoid URL-reserved characters
  (`@ : / ?`) — the chart embeds it into a connection string. An auto-generated
  password (leave it empty) is URL-safe and preserved across upgrades.
- The AI service and the database are never exposed via the ingress; enable
  `networkPolicy` to enforce that at the network layer too.
