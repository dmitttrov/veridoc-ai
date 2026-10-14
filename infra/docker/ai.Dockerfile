# Veridoc AI inference service (FastAPI). Internal-only; no host port is
# published for it in docker-compose.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install the package and its runtime dependencies.
COPY services/ai/pyproject.toml ./
COPY services/ai/app ./app
RUN pip install --no-cache-dir .

# Drop privileges: create and switch to a non-root user (never run as root).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Apply any pending migrations, then serve. (Idempotent; safe to re-run.)
CMD ["sh", "-c", "python -m app.db.migrate && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
