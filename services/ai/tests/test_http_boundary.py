"""HTTP-boundary tests for the DB-backed endpoints: the 503 (no DB), 415
(bad MIME), and 422 (bad input) branches that unit tests never reach."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


class _FakePool:
    """Truthy pool so _require_pool passes; never actually queried in these tests."""

    async def close(self) -> None:  # called by lifespan shutdown
        return None


def test_ingest_returns_503_without_db() -> None:
    with TestClient(app) as client:
        app.state.pool = None
        resp = client.post(
            "/v1/documents/ingest",
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "database_unavailable"


def test_retrieve_returns_503_without_db() -> None:
    with TestClient(app) as client:
        app.state.pool = None
        resp = client.post("/v1/retrieve", json={"query": "revenue"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "database_unavailable"


def test_rag_returns_503_without_db() -> None:
    with TestClient(app) as client:
        app.state.pool = None
        resp = client.post("/v1/rag/answer", json={"question": "What was revenue?"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "database_unavailable"


def test_ingest_rejects_non_pdf_with_415() -> None:
    with TestClient(app) as client:
        app.state.pool = _FakePool()
        resp = client.post(
            "/v1/documents/ingest",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
    assert resp.status_code == 415
    assert resp.json()["detail"]["code"] == "unsupported_media_type"


def test_retrieve_rejects_non_uuid_document_ids_with_422() -> None:
    # document_ids flow straight into the DB as UUIDs; a non-UUID must be a 422
    # at the contract boundary, not a 500 deep in retrieval.
    with TestClient(app) as client:
        resp = client.post(
            "/v1/retrieve",
            json={"query": "revenue", "documentIds": ["not-a-uuid"]},
        )
    assert resp.status_code == 422


def test_rag_rejects_non_uuid_document_ids_with_422() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/v1/rag/answer",
            json={"question": "What was revenue?", "documentIds": ["not-a-uuid"]},
        )
    assert resp.status_code == 422
