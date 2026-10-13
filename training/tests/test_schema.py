import pytest
from pydantic import ValidationError

from veridoc_ft.schema import ExtractionResult, parse_extraction


def test_supported_requires_value_and_evidence() -> None:
    ExtractionResult(metric="revenue", value="482.6", unit="USD millions",
                     period="FY2023", evidence="E1", supported=True)
    with pytest.raises(ValueError):
        ExtractionResult(metric="revenue", supported=True)  # missing value/evidence


def test_unsupported_requires_nulls() -> None:
    ExtractionResult(metric="revenue", supported=False)
    with pytest.raises(ValueError):
        ExtractionResult(metric="revenue", value="5", supported=False)


def test_extra_keys_forbidden() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(
            {"metric": "x", "supported": False, "hallucinated": 1}
        )


def test_parse_statuses() -> None:
    ok = ExtractionResult(
        metric="revenue", value="482.6", unit="USD millions",
        period="FY2023", evidence="E1", supported=True,
    ).to_json()
    r, status = parse_extraction("Here: " + ok + " done")
    assert status == "ok" and r is not None and r.value == "482.6"

    r, status = parse_extraction("no json here")
    assert status == "no_json" and r is None

    r, status = parse_extraction("{not valid json}")
    assert status == "invalid_json"

    r, status = parse_extraction('{"metric":"x","supported":true}')  # violates invariant
    assert status == "schema_invalid"
