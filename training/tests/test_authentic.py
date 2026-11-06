"""Unit tests for the authentic filing-text harness (no GPU/network/DB)."""
from __future__ import annotations

import json
from pathlib import Path

from veridoc_ft.config import TrainConfig
from veridoc_ft.realeval.authentic import (
    FilingSpec,
    GoldItem,
    _canon_digits,
    html_to_text,
    paginate,
    passage_has_gold_digits,
    run_authentic,
    score_authentic,
    select_gold,
)
from veridoc_ft.realeval.dataset import RealExample
from veridoc_ft.realeval.e2e import GatewayClient

# --- html_to_text ------------------------------------------------------------

FILING_HTML = """
<html><head><title>10-K</title><style>p{color:red}</style></head>
<body>
<div style="display:none"><ix:header>HIDDEN-XBRL 999,999</ix:header></div>
<script>var leak = "SCRIPT-LEAK";</script>
<p>Total net sales increased 2%&nbsp;or $7,750 million during 2024.</p>
<table>
<tr><td>Products</td><td></td><td>$</td><td>294,866</td><td></td><td>$</td><td>298,085</td></tr>
<tr><td>Total net sales</td><td></td><td>$</td><td>391,035</td><td></td>
<td>$</td><td>383,285</td></tr>
</table>
</body></html>
"""


def test_html_tables_become_pipe_separated_rows() -> None:
    text = html_to_text(FILING_HTML)
    assert "Total net sales | $ | 391,035 | $ | 383,285" in text
    assert "Products | $ | 294,866" in text


def test_hidden_and_script_content_is_dropped() -> None:
    text = html_to_text(FILING_HTML)
    assert "HIDDEN-XBRL" not in text  # inline-XBRL must not leak into evidence
    assert "SCRIPT-LEAK" not in text
    assert "10-K" not in text  # <title> skipped


def test_entities_and_nbsp_are_decoded() -> None:
    text = html_to_text(FILING_HTML)
    assert "2% or $7,750 million" in text


def test_unclosed_tags_in_hidden_subtree_do_not_swallow_the_document() -> None:
    # HTML legally omits </p>/<td> closes; a bare depth counter would never
    # return to zero and silently drop ALL remaining filing text.
    html = (
        '<div style="display:none"><p>ctx1<p>ctx2</div>'
        "<p>Total net sales</p><table><tr><td>391,035</td></tr></table>"
    )
    text = html_to_text(html)
    assert "Total net sales" in text and "391,035" in text
    assert "ctx1" not in text


def test_stray_end_tag_inside_hidden_container_does_not_leak() -> None:
    html = '<div style="display:none">SECRET-1</b> SECRET-2</div>AFTER'
    text = html_to_text(html)
    assert "SECRET-1" not in text and "SECRET-2" not in text
    assert "AFTER" in text


def test_omitted_head_close_does_not_swallow_the_body() -> None:
    html = "<html><head><title>x</title><body><p>BODY TEXT</p></body></html>"
    assert "BODY TEXT" in html_to_text(html)


def test_hidden_detection_survives_whitespace_variants() -> None:
    assert "HIDDEN" not in html_to_text('<div style="display:\nnone">HIDDEN</div>VIS')
    assert "HIDDEN" not in html_to_text('<div style="visibility: hidden">HIDDEN</div>VIS')


def test_unicode_spaces_are_normalized_for_wrapping() -> None:
    # En/em/thin/narrow-no-break spaces must become plain spaces, or _wrap
    # treats the whole run as one unbreakable word.
    text = html_to_text("<p>alpha&#8194;beta&#8201;gamma&#8239;delta</p>")
    assert text == "alpha beta gamma delta"


# --- paginate ----------------------------------------------------------------


def test_pages_respect_size_and_are_deterministic() -> None:
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(300))
    pages = paginate(text, page_chars=500)
    assert pages == paginate(text, page_chars=500)
    assert all(len(p) <= 500 + 60 for p in pages)
    assert "".join(pages).count("line 299") == 1  # nothing dropped


def test_pages_never_exceed_the_rendered_line_capacity() -> None:
    # One logical page must fit one physical LETTER page (46 lines), or the
    # PDF gains overflow pages and busts the gateway's 300-page limit.
    text = "\n".join("r" for _ in range(500))  # 500 one-char lines
    pages = paginate(text, page_chars=100_000)
    assert all(len(p.splitlines()) <= 46 for p in pages)


def test_long_paragraph_lines_are_wrapped_below_pdf_limit() -> None:
    # The PDF renderer truncates lines at 200 chars; unwrapped prose would
    # silently lose filing text (and with it, gold values).
    text = "word " * 400  # one ~2000-char line
    pages = paginate(text.strip(), page_chars=2800)
    assert all(len(line) <= 200 for page in pages for line in page.splitlines())
    assert sum(page.count("word") for page in pages) == 400


def test_space_free_runs_are_hard_sliced_not_truncated() -> None:
    # Dot leaders / long identifiers have no spaces; they must be sliced, not
    # handed to the renderer to cut at 200 chars.
    token = "A" * 450
    pages = paginate(token, page_chars=2800)
    lines = [line for page in pages for line in page.splitlines()]
    assert all(len(line) <= 200 for line in lines)
    assert sum(line.count("A") for line in lines) == 450


# --- digit matching ----------------------------------------------------------


def test_gold_digits_match_table_token_without_scale_word() -> None:
    gold = {"value": "391,035", "unit": "USD millions"}
    assert passage_has_gold_digits("Total net sales | $ | 391,035 | 383,285", gold)


def test_adjacent_cells_do_not_concatenate_into_false_positive() -> None:
    gold = {"value": "3910", "unit": "USD millions"}
    # "39" and "10" are adjacent tokens; only a single token may match.
    assert not passage_has_gold_digits("segment | 39 | 10 | total", gold)


def test_small_numbers_never_match() -> None:
    assert not passage_has_gold_digits("fiscal 2024 results", {"value": "202", "unit": "USD"})


def test_canon_digits_strips_only_trailing_zero_decimals() -> None:
    # "(391,035.0)" is the same printed number as "391,035"; "3,910.35" is NOT
    # the same printed number as "3,910" — truncating at '.' would credit it.
    assert _canon_digits("(391,035.0)") == "391035"
    assert _canon_digits("3,910.35") == "391035"
    assert _canon_digits("3,910.35") != _canon_digits("3,910")
    assert _canon_digits(None) == ""


def test_year_shaped_gold_is_excluded_from_digits_regime() -> None:
    # A $2,023M gold would digit-match every fiscal-year date token.
    s = score_authentic(
        GoldItem(company="X", metric="m", period="FY2023",
                 value="2,023", unit="USD millions"),
        ["for the fiscal year ended December 31, 2023"],
        _pred("2,023", "USD millions", "E1", True, metric="m"),
    )
    assert "retrieval_hit_digits" not in s
    assert "value_digits_exact" not in s
    assert "citation_support_digits" not in s


# --- select_gold -------------------------------------------------------------


def _example(company: str, cik: str, metric: str, period: str, value: str,
             unit: str = "USD millions", end: str = "2025-09-27",
             accession: str = "0001-25-000073") -> RealExample:
    return RealExample(
        id=f"{cik}|{metric}|{period}|answerable",
        company=company, category="answerable",
        question=f"What was {company}'s {metric} for {period}?",
        evidence=[f"For {period}, {company} reported {metric} of ${value} million."],
        target={"metric": metric, "value": value, "unit": unit, "period": period,
                "evidence": "E1", "supported": True},
        provenance={"cik": cik, "accession": accession, "period_end": end},
    )


def test_select_gold_uses_latest_filing_and_two_fiscal_years() -> None:
    examples = [
        _example("Apple Inc.", "0000320193", "total revenue", "FY2024", "391,035",
                 end="2024-09-28", accession="0001-24-000123"),
        _example("Apple Inc.", "0000320193", "total revenue", "FY2025", "416,161",
                 end="2025-09-27", accession="0001-25-000073"),
        _example("Apple Inc.", "0000320193", "net income", "FY2023", "96,995",
                 end="2023-09-30", accession="0001-23-000106"),  # outside FY/FY-1
    ]
    specs = select_gold(examples)
    assert len(specs) == 1
    spec = specs[0]
    assert spec.accession == "0001-25-000073"  # latest 10-K wins
    assert {i.period for i in spec.items} == {"FY2024", "FY2025"}


def test_select_gold_excludes_raw_dollar_targets() -> None:
    examples = [_example("Acme", "1", "total revenue", "FY2025", "1,234,567", unit="USD")]
    assert select_gold(examples) == []


# --- scoring -----------------------------------------------------------------

ITEM = GoldItem(company="Apple Inc.", metric="total revenue", period="FY2025",
                value="416,161", unit="USD millions")
TABLE_ROW = "Total net sales | $ | 416,161 | $ | 391,035"


def _pred(value: str | None, unit: str | None, evidence: str | None,
          supported: bool, metric: str = "total revenue") -> dict:
    result = {"metric": metric, "value": value, "unit": unit,
              "period": "FY2025" if supported else None,
              "evidence": evidence, "supported": supported}
    return {"raw": json.dumps(result), "status": "ok", "result": result, "latency_s": 0.01}


def test_digits_regime_credits_scale_free_table_read() -> None:
    s = score_authentic(ITEM, [TABLE_ROW], _pred("416,161", "USD", "E1", True))
    assert s["retrieval_hit_digits"] is True
    assert s["value_digits_exact"] is True
    assert s["value_exact"] is False  # scale-aware: "USD" raw ≠ gold millions
    assert s["citation_valid"] is True
    assert s["citation_support_digits"] is True


def test_scale_aware_regime_credits_explicit_millions() -> None:
    s = score_authentic(ITEM, [TABLE_ROW], _pred("416,161", "USD millions", "E1", True))
    assert s["value_exact"] is True and s["value_digits_exact"] is True


def test_abstention_counts_against_coverage_not_digits() -> None:
    s = score_authentic(ITEM, [TABLE_ROW], _pred(None, None, None, False))
    assert s["pred_supported"] is False
    assert s["value_digits_exact"] is False


# --- run_authentic with fakes --------------------------------------------------


class FakeGateway(GatewayClient):
    def __init__(self, retrieved_texts: list[str], reranked: bool | None = None) -> None:
        super().__init__("http://fake")
        self.retrieved_texts = retrieved_texts
        self.uploads: list[str] = []
        self.scopes: list[list[str] | None] = []
        self._reranked = reranked

    def upload_pdf(self, filename: str, data: bytes) -> str:
        assert data.startswith(b"%PDF")
        self.uploads.append(filename)
        return f"doc-{len(self.uploads)}"

    def retrieve(self, query: str, top_k: int, rerank: bool | None,
                 document_ids: list[str] | None = None) -> list[dict]:
        self.scopes.append(document_ids)
        reranked = bool(rerank) if self._reranked is None else self._reranked
        self.last_response_meta = {"embedding_model": "fake-emb", "reranked": reranked}
        return [{"text": t, "citation": f"fake, p.{i + 1}"}
                for i, t in enumerate(self.retrieved_texts[:top_k])]


def _good_extract(question: str, evidence: list[str]) -> dict:
    for i, text in enumerate(evidence):
        if "416,161" in text:
            return _pred("416,161", "USD", f"E{i + 1}", True)
    return _pred(None, None, None, False)


def test_run_authentic_end_to_end_with_fakes(tmp_path: Path) -> None:
    spec = FilingSpec(company="Apple Inc.", cik="0000320193",
                      accession="0001-25-000073", items=(ITEM,))
    out = tmp_path / "report.json"
    report = run_authentic(
        TrainConfig(),
        data_path="unused",
        rerank=True,
        out_path=str(out),
        client=FakeGateway([TABLE_ROW, "unrelated prose about risk factors"]),
        extract_fn=_good_extract,
        specs=[spec],
        filing_text={"Apple Inc.": "Some prose.\n" + TABLE_ROW},
    )
    m = report["metrics"]
    assert m["retrieval_hit_digits_rate"] == 1.0
    assert m["value_digits_exact_rate"] == 1.0
    assert m["value_exact"] == 0.0  # scale unknown from the chunk alone
    assert m["false_abstention_rate"] == 0.0
    assert report["retrieval_meta"]["embedding_model"] == "fake-emb"
    assert report["corpus"][0]["pages"] >= 1
    assert json.loads(out.read_text(encoding="utf-8"))["mode"] == "authentic-filing-text"


def test_run_authentic_counts_retrieval_miss(tmp_path: Path) -> None:
    spec = FilingSpec(company="Apple Inc.", cik="0000320193",
                      accession="0001-25-000073", items=(ITEM,))
    report = run_authentic(
        TrainConfig(),
        data_path="unused",
        client=FakeGateway(["only risk-factor boilerplate here"]),
        extract_fn=_good_extract,
        specs=[spec],
        filing_text={"Apple Inc.": TABLE_ROW},
    )
    m = report["metrics"]
    assert m["retrieval_hit_digits_rate"] == 0.0
    assert m["value_digits_given_hit"] is None  # miss not charged to extractor
    assert m["false_abstention_rate"] == 1.0  # extractor abstained (correctly)
    assert m["parse_failure_rate"] == 0.0


def test_retrieval_is_scoped_to_this_evals_documents() -> None:
    # The store is add-only; an unscoped query could pull oracle-phrased
    # passages from another harness's corpus and fake the results.
    spec = FilingSpec(company="Apple Inc.", cik="0000320193",
                      accession="0001-25-000073", items=(ITEM,))
    gw = FakeGateway([TABLE_ROW])
    run_authentic(
        TrainConfig(), data_path="unused", client=gw, extract_fn=_good_extract,
        specs=[spec], filing_text={"Apple Inc.": TABLE_ROW},
    )
    assert gw.scopes == [["doc-1"]]


def test_rerank_on_without_a_reranker_fails_loudly() -> None:
    spec = FilingSpec(company="Apple Inc.", cik="0000320193",
                      accession="0001-25-000073", items=(ITEM,))
    try:
        run_authentic(
            TrainConfig(), data_path="unused", rerank=True,
            client=FakeGateway([TABLE_ROW], reranked=False),
            extract_fn=_good_extract, specs=[spec],
            filing_text={"Apple Inc.": TABLE_ROW},
        )
        raise AssertionError("expected RuntimeError for silently-skipped rerank")
    except RuntimeError as exc:
        assert "rerank" in str(exc)


def test_retrieval_only_mode_measures_without_a_model() -> None:
    # No extract_fn, no adapter, retrieval_only=True: must never touch torch.
    spec = FilingSpec(company="Apple Inc.", cik="0000320193",
                      accession="0001-25-000073", items=(ITEM,))
    report = run_authentic(
        TrainConfig(), data_path="unused", retrieval_only=True,
        client=FakeGateway([TABLE_ROW]),
        specs=[spec], filing_text={"Apple Inc.": TABLE_ROW},
    )
    m = report["metrics"]
    assert report["mode"] == "authentic-retrieval-only"
    assert m["retrieval_hit_digits_rate"] == 1.0
    assert m["value_exact"] is None  # extraction keys absent, reported null
    assert m["parse_failure_rate"] is None
    assert report["model_id"] is None


def test_citation_support_digits_is_aggregated() -> None:
    spec = FilingSpec(company="Apple Inc.", cik="0000320193",
                      accession="0001-25-000073", items=(ITEM,))
    report = run_authentic(
        TrainConfig(), data_path="unused",
        client=FakeGateway([TABLE_ROW]), extract_fn=_good_extract,
        specs=[spec], filing_text={"Apple Inc.": TABLE_ROW},
    )
    assert report["metrics"]["citation_support_digits_rate"] == 1.0
    assert report["metrics"]["n_digits_excluded"] == 0
    assert report["corpus"][0]["source_document"] == "injected"
