"""Unit tests for the end-to-end RAG real-eval harness (no GPU/network/DB).

The gateway and the extraction model are faked; these tests pin down the
harness's own logic: corpus harvesting, facts-index parsing, gold rewriting
for corpus-answerable questions, retrieval-hit accounting, and report shape.
"""
from __future__ import annotations

import json
from pathlib import Path

from veridoc_ft.config import TrainConfig
from veridoc_ft.realeval.dataset import RealExample
from veridoc_ft.realeval.e2e import (
    GatewayClient,
    build_pdf,
    harvest_corpus,
    resolve_e2e_target,
    run_e2e,
)

APPLE = "Apple Inc."
REV_FY23 = "For FY2023, Apple Inc. reported total revenue of $383,285 million."
NI_FY23 = "For FY2023, Apple Inc. reported net income of $96,995 million."
OCF_NEG = "For FY2023, Apple Inc. reported net cash from operating activities of $(1,234) million."


def _answerable(metric: str = "total revenue", value: str = "383,285") -> RealExample:
    return RealExample(
        id=f"ap|{metric}|FY2023|answerable",
        company=APPLE,
        category="answerable",
        question=f"What was {APPLE}'s {metric} for FY2023?",
        evidence=[NI_FY23, REV_FY23],
        target={"metric": metric, "value": value, "unit": "USD millions",
                "period": "FY2023", "evidence": "E2", "supported": True},
        provenance={"period_end": "2023-09-30"},
    )


def _unanswerable(asked_metric: str) -> RealExample:
    return RealExample(
        id=f"ap|{asked_metric}|FY2023|unanswerable",
        company=APPLE,
        category="unanswerable",
        question=f"What was {APPLE}'s {asked_metric} for FY2023?",
        evidence=[REV_FY23],
        target={"metric": asked_metric, "value": None, "unit": None,
                "period": None, "evidence": None, "supported": False},
        provenance={"period_end": "2023-09-30"},
    )


# --- harvest_corpus ----------------------------------------------------------


def test_corpus_pages_are_deduped_and_sorted() -> None:
    pages, _ = harvest_corpus([_answerable(), _answerable()])
    assert list(pages) == [APPLE]
    assert pages[APPLE] == sorted({NI_FY23, REV_FY23})


def test_unsupported_examples_contribute_no_pages() -> None:
    pages, _ = harvest_corpus([_unanswerable("net income")])
    assert pages == {}


def test_facts_index_parses_distractor_passages_too() -> None:
    # NI_FY23 only appears as a distractor in the revenue example, but the
    # template parse still indexes it, so gold rewriting can find it.
    _, facts = harvest_corpus([_answerable()])
    key = (APPLE.lower(), "net income", "FY2023")
    assert facts[key]["value"] == "96,995"
    assert facts[key]["unit"] == "USD millions"


def test_facts_index_handles_parenthesized_negatives() -> None:
    ex = _answerable()
    ex = RealExample(**{**ex.__dict__, "evidence": [OCF_NEG, REV_FY23]})
    _, facts = harvest_corpus([ex])
    key = (APPLE.lower(), "net cash from operating activities", "FY2023")
    assert facts[key]["value"] == "(1,234)"


def test_conflicting_gold_overrides_index() -> None:
    conflicting = RealExample(
        id="ap|net income|FY2020|conflicting",
        company=APPLE,
        category="conflicting",
        question=f"What was {APPLE}'s restated net income for FY2020?",
        evidence=[
            "As originally reported, Apple Inc. net income for FY2020 was $57,000 million.",
            "Restated: Apple Inc. net income for FY2020 was revised to $57,411 million, "
            "superseding the prior figure.",
        ],
        target={"metric": "net income", "value": "57,411", "unit": "USD millions",
                "period": "FY2020", "evidence": "E2", "supported": True},
        provenance={"period_end": "2020-09-26"},
    )
    pages, facts = harvest_corpus([conflicting])
    assert len(pages[APPLE]) == 2  # both original and restated pages ingest
    assert facts[(APPLE.lower(), "net income", "FY2020")]["value"] == "57,411"


# --- resolve_e2e_target ------------------------------------------------------


def test_unanswerable_rewritten_when_fact_is_in_corpus() -> None:
    _, facts = harvest_corpus([_answerable()])
    target, rewritten = resolve_e2e_target(_unanswerable("net income"), facts)
    assert rewritten is True
    assert target["supported"] is True
    assert target["value"] == "96,995"


def test_unanswerable_stays_unanswerable_when_fact_absent() -> None:
    _, facts = harvest_corpus([_answerable()])
    target, rewritten = resolve_e2e_target(_unanswerable("total liabilities"), facts)
    assert rewritten is False
    assert target["supported"] is False


def test_supported_examples_keep_oracle_gold() -> None:
    ex = _answerable()
    _, facts = harvest_corpus([ex])
    target, rewritten = resolve_e2e_target(ex, facts)
    assert rewritten is False
    assert target == ex.target


# --- PDF determinism ---------------------------------------------------------


def test_pdf_bytes_are_deterministic() -> None:
    pages = [REV_FY23, NI_FY23]
    assert build_pdf(pages) == build_pdf(pages)
    assert build_pdf(pages).startswith(b"%PDF")


# --- run_e2e with fakes ------------------------------------------------------


class FakeGateway(GatewayClient):
    """Returns canned passages; records uploads instead of doing HTTP."""

    def __init__(self, retrieved_texts: list[str]) -> None:
        super().__init__("http://fake")
        self.retrieved_texts = retrieved_texts
        self.uploads: list[str] = []

    def upload_pdf(self, filename: str, data: bytes) -> str:
        assert data.startswith(b"%PDF")
        self.uploads.append(filename)
        return f"doc-{len(self.uploads)}"

    def retrieve(self, query: str, top_k: int, rerank: bool | None,
                 document_ids: list[str] | None = None) -> list[dict]:
        self.scopes = getattr(self, "scopes", [])
        self.scopes.append(document_ids)
        return [
            {"text": t, "citation": f"fake, p.{i + 1}"}
            for i, t in enumerate(self.retrieved_texts[:top_k])
        ]


def _good_extractor(question: str, evidence: list[str]) -> dict:
    """Cites whichever retrieved passage mentions revenue; abstains otherwise."""
    for i, text in enumerate(evidence):
        if "total revenue" in text:
            result = {"metric": "total revenue", "value": "383,285",
                      "unit": "USD millions", "period": "FY2023",
                      "evidence": f"E{i + 1}", "supported": True}
            return {"raw": json.dumps(result), "status": "ok",
                    "result": result, "latency_s": 0.01}
    result = {"metric": "total revenue", "value": None, "unit": None,
              "period": None, "evidence": None, "supported": False}
    return {"raw": json.dumps(result), "status": "ok", "result": result, "latency_s": 0.01}


def test_run_e2e_scores_retrieval_hit_and_extraction(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    gw = FakeGateway([NI_FY23, REV_FY23])
    report = run_e2e(
        TrainConfig(),
        data_path=_write_data(tmp_path, [_answerable()]),
        client=gw,
        extract_fn=_good_extractor,
        out_path=str(out),
    )
    m = report["metrics"]
    assert m["retrieval_hit_rate"] == 1.0
    assert m["value_exact"] == 1.0
    assert m["value_exact_given_hit"] == 1.0
    assert m["citation_valid"] == 1.0
    assert m["citation_support"] == 1.0
    assert report["mode"] == "e2e"
    assert report["corpus"]["documents"] == 1
    # Retrieval must be scoped to this eval's own uploaded documents — the
    # store is add-only and may hold other corpora.
    assert gw.scopes == [["doc-1"]]
    assert json.loads(out.read_text(encoding="utf-8"))["metrics"]["value_exact"] == 1.0


def test_run_e2e_counts_retrieval_miss_without_blaming_extractor(tmp_path: Path) -> None:
    # Retrieval returns only the distractor: the extractor correctly abstains.
    # The miss must show up in retrieval_hit_rate, and value_exact_given_hit
    # must be None (no hits) rather than charging the extractor with a miss.
    report = run_e2e(
        TrainConfig(),
        data_path=_write_data(tmp_path, [_answerable()]),
        client=FakeGateway([NI_FY23]),
        extract_fn=_good_extractor,
    )
    m = report["metrics"]
    assert m["retrieval_hit_rate"] == 0.0
    assert m["value_exact"] == 0.0
    assert m["value_exact_given_hit"] is None


def test_run_e2e_rewrites_unanswerable_against_corpus(tmp_path: Path) -> None:
    # The oracle-unanswerable "net income" question IS answerable from the
    # corpus; the harness must expect an answer, so the abstaining extractor
    # scores a value miss here, not an abstention win.
    data = _write_data(tmp_path, [_answerable(), _unanswerable("net income")])
    report = run_e2e(
        TrainConfig(),
        data_path=data,
        client=FakeGateway([NI_FY23, REV_FY23]),
        extract_fn=_good_extractor,
    )
    m = report["metrics"]
    assert m["n_rewritten_unanswerable"] == 1
    assert m["n_unsupported"] == 0  # both examples are supported in e2e mode
    assert m["value_exact"] == 0.5  # revenue answered; rewritten NI abstained
    rewritten = [d for d in report["details"] if d["rewritten"]]
    assert len(rewritten) == 1 and rewritten[0]["category"] == "unanswerable"


def _write_data(tmp_path: Path, examples: list[RealExample]) -> str:
    path = tmp_path / "real_test.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for ex in examples:
            fh.write(json.dumps(ex.__dict__, sort_keys=True) + "\n")
    return str(path)
