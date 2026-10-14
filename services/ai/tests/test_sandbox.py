"""Process-sandboxed PDF parsing: correct result, error propagation across the
process boundary, and an actually-enforced (killable) timeout."""
from __future__ import annotations

import time

import pytest

from app.eval.pdf_build import NON_PDF_BYTES, build_pdf
from app.ingestion.errors import PdfMalformed, PdfProcessingTimeout
from app.ingestion.sandbox import _run_in_process, extract_pdf_sandboxed

LIMITS = {"max_bytes": 25 * 1024 * 1024, "max_pages": 300}


async def test_extracts_in_child_process() -> None:
    pdf = build_pdf(["Total revenue was 482.6 million dollars.", "Second page."])
    result = await extract_pdf_sandboxed(pdf, timeout_s=30.0, **LIMITS)
    assert result.page_count == 2
    assert "revenue" in result.page_texts[0].lower()


async def test_worker_errors_propagate_across_process_boundary() -> None:
    with pytest.raises(PdfMalformed):
        await extract_pdf_sandboxed(NON_PDF_BYTES, timeout_s=30.0, **LIMITS)


async def test_timeout_is_enforced_and_raises() -> None:
    # time.sleep is a top-level builtin (picklable + importable by a spawned
    # child), so this exercises the real cross-process timeout + kill path.
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        await _run_in_process(time.sleep, 30, timeout_s=0.3)
    # Returns promptly rather than waiting out the full 30s sleep.
    assert time.monotonic() - start < 10.0


async def test_extract_timeout_maps_to_processing_timeout() -> None:
    # A tiny timeout on a real (if fast) parse maps to the typed ingestion error.
    pdf = build_pdf(["x"])
    with pytest.raises(PdfProcessingTimeout):
        await extract_pdf_sandboxed(pdf, timeout_s=0.0, **LIMITS)
