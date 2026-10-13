import re

from veridoc_ft.realeval.dev_regression import build_dev_set
from veridoc_ft.realeval.normalize import values_match
from veridoc_ft.schema import ExtractionResult


def test_dev_set_schema_and_citations_valid() -> None:
    for ex in build_dev_set():
        r = ExtractionResult.model_validate(ex.target)
        markers = {f"E{i + 1}" for i in range(len(ex.evidence))}
        if r.supported:
            assert r.evidence in markers
            # gold value genuinely appears in the cited passage
            idx = int(r.evidence[1:]) - 1
            nums = re.findall(r"\$?\(?-?[\d,]+(?:\.\d+)?\)?", ex.evidence[idx])
            assert any(values_match(n, r.unit, r.value, r.unit) for n in nums), ex.id


def test_dev_abstention_examples_truly_unsupported() -> None:
    for ex in build_dev_set():
        if not ex.target["supported"]:
            metric = ex.target["metric"].lower()
            assert all(metric not in p.lower() for p in ex.evidence), ex.id


def test_dev_covers_targeted_weaknesses() -> None:
    cats = {e.category for e in build_dev_set()}
    assert {"signed", "abstention", "metric_identity", "injection", "citation"} <= cats
