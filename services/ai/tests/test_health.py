from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_mock_mode() -> None:
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "veridoc-ai"
    assert body["mock"] is True


def test_documents_are_synthetic_fixtures() -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 1
    # Every fixture is explicitly fictional — no real company data.
    assert all("fictional" in d["issuer"].lower() for d in docs)
    assert {"id", "title", "issuer", "period", "pageCount"} <= set(docs[0].keys())
