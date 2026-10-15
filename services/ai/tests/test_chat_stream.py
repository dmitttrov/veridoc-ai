import json

from fastapi.testclient import TestClient

from app.main import app


def _parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.strip().split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:") :].strip()))
    return events


def test_chat_stream_emits_sse_events() -> None:
    with TestClient(app) as client:
        resp = client.post("/v1/chat/stream", json={"message": "What was revenue?"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse(resp.text)

    types = [e["type"] for e in events]
    assert types[0] == "token"
    assert "citations" in types
    assert types[-1] == "done"

    done = events[-1]
    assert done["mock"] is True
    assert "tokenCount" in done  # camelCase alias matches the TS contract


def test_chat_stream_rejects_empty_message() -> None:
    with TestClient(app) as client:
        resp = client.post("/v1/chat/stream", json={"message": ""})
    assert resp.status_code == 422  # Pydantic validation at the boundary
