"""Typed ingestion errors with stable, machine-readable codes.

Codes are surfaced to the gateway (and mapped to HTTP statuses there) and
recorded in `ingestion_runs.error`. Messages never contain document content.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for all expected (non-bug) ingestion failures."""

    code: str = "ingestion_failed"
    http_status: int = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PdfTooLarge(IngestionError):
    code = "pdf_too_large"
    http_status = 413


class PdfTooManyPages(IngestionError):
    code = "pdf_too_many_pages"
    http_status = 413


class PdfEncrypted(IngestionError):
    code = "pdf_encrypted"
    http_status = 422


class PdfMalformed(IngestionError):
    code = "pdf_malformed"
    http_status = 422


class UnsupportedMediaType(IngestionError):
    code = "unsupported_media_type"
    http_status = 415


class PdfProcessingTimeout(IngestionError):
    code = "pdf_processing_timeout"
    http_status = 504
