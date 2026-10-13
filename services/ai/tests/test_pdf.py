import pytest

from app.eval.pdf_build import (
    MALFORMED_PDF_BYTES,
    NON_PDF_BYTES,
    build_blank_pdf,
    build_encrypted_pdf,
    build_pdf,
)
from app.ingestion.errors import (
    PdfEncrypted,
    PdfMalformed,
    PdfTooLarge,
    PdfTooManyPages,
)
from app.ingestion.pdf import validate_and_extract

LIMITS = {"max_bytes": 25 * 1024 * 1024, "max_pages": 300}


def test_extracts_text_and_page_count() -> None:
    pdf = build_pdf(["Total revenue was 482.6 million dollars.", "Second page text."])
    result = validate_and_extract(pdf, **LIMITS)
    assert result.page_count == 2
    assert "revenue" in result.page_texts[0].lower()


def test_rejects_non_pdf_signature() -> None:
    with pytest.raises(PdfMalformed):
        validate_and_extract(NON_PDF_BYTES, **LIMITS)


def test_rejects_malformed_pdf() -> None:
    with pytest.raises(PdfMalformed):
        validate_and_extract(MALFORMED_PDF_BYTES, **LIMITS)


def test_rejects_empty_file() -> None:
    with pytest.raises(PdfMalformed):
        validate_and_extract(b"", **LIMITS)


def test_rejects_encrypted_pdf() -> None:
    pdf = build_encrypted_pdf(["secret financials"], password="secret")
    with pytest.raises(PdfEncrypted):
        validate_and_extract(pdf, **LIMITS)


def test_rejects_oversized_file() -> None:
    pdf = build_pdf(["x"])
    with pytest.raises(PdfTooLarge):
        validate_and_extract(pdf, max_bytes=10, max_pages=300)


def test_rejects_too_many_pages() -> None:
    pdf = build_pdf(["p1", "p2", "p3"])
    with pytest.raises(PdfTooManyPages):
        validate_and_extract(pdf, max_bytes=LIMITS["max_bytes"], max_pages=2)


def test_blank_pages_extract_empty_text() -> None:
    pdf = build_blank_pdf(2)
    result = validate_and_extract(pdf, **LIMITS)
    assert result.page_count == 2
    assert all(text.strip() == "" for text in result.page_texts)
