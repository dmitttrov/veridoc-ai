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


def test_readyz_degraded_without_db() -> None:
    # Liveness stays ok, but readiness must report degraded + 503 when the pool
    # is unavailable, so an orchestrator does not route DB-backed traffic here.
    with TestClient(app) as client:
        app.state.pool = None
        resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


class _FakeConn:
    async def fetchval(self, _query: str) -> int:
        return 1


class _FakeAcquire:
    async def __aenter__(self) -> _FakeConn:
        return _FakeConn()

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakePool:
    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire()

    async def close(self) -> None:  # called by the lifespan shutdown
        return None


def test_readyz_ok_when_db_reachable() -> None:
    with TestClient(app) as client:
        app.state.pool = _FakePool()
        resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_lifespan_closes_created_pool_even_when_state_pool_swapped(monkeypatch) -> None:
    # Regression: the lifespan must close the pool IT created, even if a test (or
    # caller) swaps app.state.pool afterwards. Otherwise the real asyncpg pool is
    # orphaned and its connections leak, surfacing as a ResourceWarning at GC
    # (which pytest's unraisableexception + filterwarnings=error turns into a
    # failure in whatever test happens to be running).
    closed = {"value": False}

    class _TrackingPool(_FakePool):
        async def close(self) -> None:
            closed["value"] = True

    async def _fake_create_pool(_settings: object) -> _TrackingPool:
        return _TrackingPool()

    monkeypatch.setattr("app.main.create_pool", _fake_create_pool)
    with TestClient(app) as client:
        # Mimic the degraded-path swap the other readiness tests perform.
        app.state.pool = None
        client.get("/health")
    assert closed["value"] is True


def test_request_id_is_generated_and_echoed() -> None:
    with TestClient(app) as client:
        generated = client.get("/health")
        echoed = client.get("/health", headers={"x-request-id": "abc-123_ID"})
    assert generated.headers.get("x-request-id")  # a fresh id was minted
    assert echoed.headers.get("x-request-id") == "abc-123_ID"  # safe inbound id reused


def test_unsafe_inbound_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        resp = client.get("/health", headers={"x-request-id": "bad id with spaces!"})
    rid = resp.headers.get("x-request-id")
    assert rid and rid != "bad id with spaces!"


def test_documents_are_synthetic_fixtures() -> None:
    with TestClient(app) as client:
        resp = client.get("/v1/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 1
    # Every fixture is explicitly fictional — no real company data.
    assert all("fictional" in d["issuer"].lower() for d in docs)
    assert {"id", "title", "issuer", "period", "pageCount"} <= set(docs[0].keys())
