"""Build synthetic PDF bytes for tests and evaluation (reportlab, BSD).

All content is fictional. reportlab is a dev-only dependency and is imported
lazily so importing this module never requires it unless a PDF is actually
built. Also provides deliberately broken/encrypted inputs for negative tests.
"""
from __future__ import annotations

from io import BytesIO

# A structurally invalid file that nonetheless starts with the PDF signature.
MALFORMED_PDF_BYTES = b"%PDF-1.4\nthis is not a valid pdf body\n%%EOF"
# A file with no PDF signature at all.
NON_PDF_BYTES = b"Just some plain text, definitely not a PDF."


def _wrap(text: str, width: int = 95) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > width:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        lines.append(current)
    return lines


def build_pdf(pages: list[str]) -> bytes:
    """Render each string in ``pages`` as its own PDF page of text.

    ``invariant=1`` makes reportlab emit byte-for-byte identical output for the
    same input (fixed timestamps and document id). That determinism is essential:
    it gives a stable SHA-256 content hash, which is what makes ingestion
    idempotent and the evaluation reproducible.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER, invariant=1)
    width, height = LETTER
    for text in pages:
        y = height - 72
        for line in _wrap(text):
            if y < 72:
                c.showPage()
                y = height - 72
            c.drawString(72, y, line)
            y -= 14
        c.showPage()
    c.save()
    return buf.getvalue()


def build_blank_pdf(num_pages: int = 1) -> bytes:
    """A PDF with pages but no extractable text (e.g. a scanned-image stand-in)."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER, invariant=1)
    for _ in range(num_pages):
        c.showPage()
    c.save()
    return buf.getvalue()


def build_encrypted_pdf(pages: list[str], password: str = "secret") -> bytes:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(build_pdf(pages)))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()
