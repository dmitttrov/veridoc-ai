"""Secure PDF validation and text extraction (pypdf, BSD-3-Clause).

Security posture (see docs/SECURITY.md):
  * Extracted text is treated as untrusted DATA. It is never executed, eval'd,
    or interpreted as instructions anywhere in the pipeline.
  * Document content is never logged.
  * Size, page-count, encryption, and malformed-file checks run before any
    expensive work; the caller additionally enforces a wall-clock timeout.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.ingestion.errors import (
    PdfEncrypted,
    PdfMalformed,
    PdfTooLarge,
    PdfTooManyPages,
)

_PDF_MAGIC = b"%PDF-"


@dataclass(frozen=True)
class ExtractedPdf:
    page_count: int
    #: Raw (un-normalized) text per page, index 0 == page 1.
    page_texts: list[str]


def _assert_signature(data: bytes) -> None:
    # A valid PDF begins with "%PDF-" within the first bytes. This cheaply
    # rejects non-PDF uploads before handing bytes to the parser.
    head = data[:1024].lstrip()
    if not head.startswith(_PDF_MAGIC):
        raise PdfMalformed("File does not start with a PDF signature.")


def validate_and_extract(
    data: bytes,
    *,
    max_bytes: int,
    max_pages: int,
) -> ExtractedPdf:
    """Validate a PDF and extract per-page text.

    Raises a subclass of ``IngestionError`` for any expected rejection
    (too large, too many pages, encrypted, malformed). This function is
    synchronous and CPU-bound; callers run it under a timeout.
    """
    if len(data) == 0:
        raise PdfMalformed("Uploaded file is empty.")
    if len(data) > max_bytes:
        raise PdfTooLarge(
            f"File is {len(data)} bytes; limit is {max_bytes} bytes."
        )

    _assert_signature(data)

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except PyPdfError as exc:
        raise PdfMalformed("The file could not be parsed as a valid PDF.") from exc
    except Exception as exc:  # pypdf can raise assorted low-level errors
        raise PdfMalformed("The file could not be parsed as a valid PDF.") from exc

    # Reject encrypted documents rather than attempting decryption.
    if reader.is_encrypted:
        raise PdfEncrypted("Encrypted PDFs are not accepted.")

    try:
        page_count = len(reader.pages)
    except PyPdfError as exc:
        raise PdfMalformed("The PDF page tree is invalid.") from exc

    if page_count == 0:
        raise PdfMalformed("The PDF contains no pages.")
    if page_count > max_pages:
        raise PdfTooManyPages(
            f"PDF has {page_count} pages; limit is {max_pages}."
        )

    page_texts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # a single bad page should not be silent
            raise PdfMalformed("Failed to extract text from a page.") from exc
        page_texts.append(text)

    return ExtractedPdf(page_count=page_count, page_texts=page_texts)
