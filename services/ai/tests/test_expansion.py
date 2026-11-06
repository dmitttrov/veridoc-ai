"""Unit + DB-gated tests for metric-synonym query expansion (ADR-0028)."""
from __future__ import annotations

from app.models import RetrievalRequest
from app.retrieval.expansion import DEFAULT_MAX_VARIANTS, expand_query
from app.retrieval.service import retrieve
from tests.conftest import requires_db

# --- expand_query (pure) -----------------------------------------------------


def test_original_query_always_comes_first() -> None:
    variants = expand_query("What was Apple's total revenue for FY2025?")
    assert variants[0] == "What was Apple's total revenue for FY2025?"
    assert len(variants) > 1


def test_filing_vocabulary_variants_are_generated() -> None:
    variants = expand_query("What was Apple's total revenue for FY2025?")
    assert "What was Apple's total net sales for FY2025?" in variants


def test_no_metric_phrase_returns_only_the_original() -> None:
    assert expand_query("What were the main risk factors?") == [
        "What were the main risk factors?"
    ]


def test_longest_phrase_wins() -> None:
    # "net cash from operating activities" contains no shorter group phrase
    # that should shadow it; the OCF group must drive the variants.
    variants = expand_query("net cash from operating activities in FY2024")
    assert "net cash provided by operating activities in FY2024" in variants


def test_word_boundaries_prevent_partial_matches() -> None:
    # "revenues" inside "nonrevenues" must not match.
    assert expand_query("nonrevenues item") == ["nonrevenues item"]


def test_variant_count_is_capped_and_deduplicated() -> None:
    variants = expand_query("total revenue", max_variants=3)
    assert len(variants) == 3
    assert len(set(variants)) == 3
    assert len(expand_query("total revenue")) <= DEFAULT_MAX_VARIANTS


def test_expansion_is_deterministic() -> None:
    q = "stockholders equity at year end"
    assert expand_query(q) == expand_query(q)


def test_case_insensitive_matching_preserves_surrounding_text() -> None:
    variants = expand_query("TOTAL REVENUE for the year")
    assert variants[0] == "TOTAL REVENUE for the year"
    assert any("total net sales for the year" in v for v in variants)


# --- retrieval integration (DB-gated) ----------------------------------------


@requires_db
async def test_expansion_finds_filing_vocabulary_chunks(pool, embedder, settings) -> None:
    from app.eval.pdf_build import build_pdf
    from app.ingestion.pipeline import ingest_pdf

    # A document that ONLY uses filing vocabulary — no "total revenue" anywhere.
    await ingest_pdf(
        pool, embedder, settings,
        data=build_pdf(["Total net sales | $ | 416,161 | $ | 391,035"]),
        filename="filing-vocab.pdf", mime_type="application/pdf",
    )

    request = RetrievalRequest(query="What was total revenue for FY2025?", top_k=5)
    plain = await retrieve(pool, embedder, request, None, expand_queries=False)
    expanded = await retrieve(pool, embedder, request, None, expand_queries=True)

    assert expanded.expanded_queries is not None
    assert len(expanded.expanded_queries) > 1
    assert plain.expanded_queries is None

    def hits(resp) -> bool:
        return any("416,161" in p.text for p in resp.passages)

    # With deterministic (lexical-ish hashing) embeddings, only the expanded
    # query can reach the filing-vocabulary chunk lexically.
    assert hits(expanded), "expanded retrieval must surface the net-sales row"


@requires_db
async def test_expansion_off_leaves_response_shape_unchanged(pool, embedder, settings) -> None:
    request = RetrievalRequest(query="completely unrelated query", top_k=3)
    resp = await retrieve(pool, embedder, request, None, expand_queries=True)
    # No metric phrase -> no variants -> field is null, not [query].
    assert resp.expanded_queries is None
