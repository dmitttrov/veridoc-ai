"""Synthetic, fictional document fixtures.

IMPORTANT: These are entirely made up for demonstration. They contain no real
financial data and no real company names. They exist so the end-to-end
document-list, retrieval-citation, and chat plumbing can be built and tested
before real ingestion exists.
"""
from __future__ import annotations

from app.models import Citation, DocumentSummary

FIXTURE_DOCUMENTS: list[DocumentSummary] = [
    DocumentSummary(
        id="doc-acme-fy2023",
        title="Acme Robotics — Annual Report FY2023 (sample)",
        issuer="Acme Robotics (fictional)",
        period="FY2023",
        page_count=84,
    ),
    DocumentSummary(
        id="doc-acme-fy2022",
        title="Acme Robotics — Annual Report FY2022 (sample)",
        issuer="Acme Robotics (fictional)",
        period="FY2022",
        page_count=79,
    ),
    DocumentSummary(
        id="doc-globex-q2-2024",
        title="Globex Logistics — Q2 2024 Interim Report (sample)",
        issuer="Globex Logistics (fictional)",
        period="Q2 2024",
        page_count=32,
    ),
]

_DOCUMENTS_BY_ID = {d.id: d for d in FIXTURE_DOCUMENTS}


def default_citations() -> list[Citation]:
    """A stable, deterministic citation set used by the mock provider."""
    return [
        Citation(
            document_id="doc-acme-fy2023",
            document_title="Acme Robotics — Annual Report FY2023 (sample)",
            page=12,
            snippet="Total revenue for the fiscal year was reported in the consolidated "
            "statement of operations (illustrative figures only).",
        ),
        Citation(
            document_id="doc-acme-fy2022",
            document_title="Acme Robotics — Annual Report FY2022 (sample)",
            page=11,
            snippet="Prior-year comparatives are presented for the same line items "
            "(illustrative figures only).",
        ),
    ]


def citations_for(document_ids: list[str]) -> list[Citation]:
    """Return deterministic citations limited to the requested documents.

    Falls back to the default citation set when no (known) documents are
    selected, so the citation channel is always exercised in the demo.
    """
    selected = [d for d in document_ids if d in _DOCUMENTS_BY_ID]
    if not selected:
        return default_citations()
    return [
        Citation(
            document_id=doc_id,
            document_title=_DOCUMENTS_BY_ID[doc_id].title,
            page=1,
            snippet="Selected source passage (illustrative, fixture document only).",
        )
        for doc_id in selected
    ]
