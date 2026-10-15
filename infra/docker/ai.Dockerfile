# Veridoc AI inference service (FastAPI). Internal-only; no host port is
# published for it in docker-compose.
#
# Base image pinned by digest (python:3.11-slim) for reproducible builds.
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install runtime dependencies from the hash-pinned lock FIRST — fully pinned
# and hash-verified for a reproducible image — then the package itself without
# re-resolving its dependencies. Regenerate the lock with:
#   uv pip compile pyproject.toml --python-version 3.11 --python-platform linux \
#     --generate-hashes -o requirements.lock
COPY services/ai/requirements.lock ./
RUN pip install --require-hashes -r requirements.lock

COPY services/ai/pyproject.toml ./
COPY services/ai/app ./app
RUN pip install --no-deps .

# Drop privileges: create and switch to a non-root user (never run as root).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

# Serve port is configurable. The Helm chart overrides this command to split
# migrations into an initContainer; docker-compose uses the default below.
ENV AI_PORT=8000
EXPOSE 8000

# Apply any pending migrations, then serve. Migrations are idempotent and
# advisory-locked (safe to re-run and multi-replica safe). The graceful-shutdown
# window lets in-flight SSE streams drain on SIGTERM.
CMD ["sh", "-c", "python -m app.db.migrate && uvicorn app.main:app --host 0.0.0.0 --port ${AI_PORT:-8000} --timeout-graceful-shutdown 30"]
