"""Cross-language contract check.

The Pydantic models here are hand-mirrored from the TypeScript zod contracts in
``packages/contracts``. This test validates both sides against the SAME shared
golden fixtures (``packages/contracts/wire-fixtures.json``) that the TypeScript
suite also asserts, so a field renamed/added/removed/retyped on either side
fails the round-trip in CI instead of silently drifting on the wire.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import models

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "packages" / "contracts" / "wire-fixtures.json"
)

# fixture key -> the Pydantic model that owns that wire shape.
_WIRE_MODELS = {
    "documentSummary": models.DocumentSummary,
    "chatMessage": models.ChatMessage,
    "chatRequest": models.ChatRequest,
    "citation": models.Citation,
    "tokenEvent": models.TokenEvent,
    "citationsEvent": models.CitationsEvent,
    "doneEvent": models.DoneEvent,
    "errorEvent": models.ErrorEvent,
    "healthStatus": models.HealthStatus,
    "documentIngestionResult": models.DocumentIngestionResult,
    "storedDocument": models.StoredDocument,
    "retrievalRequest": models.RetrievalRequest,
    "retrievalScores": models.RetrievalScores,
    "retrievedPassage": models.RetrievedPassage,
    "ragRequest": models.RagRequest,
    "retrievalResponse": models.RetrievalResponse,
}


@pytest.fixture(scope="module")
def fixtures() -> dict[str, Any]:
    if not _FIXTURE_PATH.exists():
        pytest.skip(f"shared wire fixture not found at {_FIXTURE_PATH} (monorepo-only check)")
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(_WIRE_MODELS))
def test_model_round_trips_wire_fixture(key: str, fixtures: dict[str, Any]) -> None:
    model = _WIRE_MODELS[key]
    instance = fixtures[key]
    # Parse the camelCase wire form, then dump back by alias. Exact equality
    # fails if a field diverged from the fixture (and thus from the TS contract).
    parsed = model.model_validate(instance)
    assert parsed.model_dump(by_alias=True) == instance


def test_fixture_covers_every_model(fixtures: dict[str, Any]) -> None:
    # A model added without a fixture (or a stale fixture key) is itself drift.
    keys = {k for k in fixtures if not k.startswith("_")}
    assert keys == set(_WIRE_MODELS)
