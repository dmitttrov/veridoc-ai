"""Deterministic text normalization.

Extracted PDF text is messy and its exact bytes vary by extractor version. We
normalize it to a stable canonical form so that:
  * chunk character offsets are meaningful and reproducible, and
  * the same document always produces the same stored text and chunks.

This function is pure and deterministic. All character offsets recorded for
chunks are relative to the OUTPUT of this function.
"""
from __future__ import annotations

import re
import unicodedata

# Collapsible horizontal whitespace (spaces, tabs, NBSP and other unicode
# spaces), but NOT newlines (which carry page structure we keep, up to a point).
_HORIZONTAL_WS = re.compile(
    "[ 	         "
    "      　]+"
)
_TRAILING_WS = re.compile(r"[ \t]+(?=\n)")
_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def normalize_text(raw: str) -> str:
    """Return a canonical, deterministic form of ``raw``.

    Steps (order matters and is fixed):
      1. Unicode NFC normalization.
      2. Normalize all line endings to ``\\n``.
      3. Drop control/format characters (except newline and tab).
      4. Collapse runs of horizontal whitespace to a single space.
      5. Strip trailing horizontal whitespace before newlines.
      6. Collapse 3+ consecutive newlines to exactly 2 (paragraph break).
      7. Strip leading/trailing whitespace of the whole text.
    """
    text = unicodedata.normalize("NFC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        ch
        for ch in text
        if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )
    text = _HORIZONTAL_WS.sub(" ", text)
    text = _TRAILING_WS.sub("", text)
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    return text.strip()
