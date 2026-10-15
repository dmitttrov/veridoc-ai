"""Robust normalization of financial values, units, and periods.

Real filings express the same magnitude many ways: "$383,285 million",
"383.285 billion", "(1,234)" for negatives, "27%" for ratios. To compare a
model's extraction against authoritative XBRL ground truth (raw integers like
383285000000) we canonicalize everything to a common representation:

  * monetary values -> Decimal in BASE UNITS (whole dollars), sign-aware;
  * percent values   -> Decimal percentage points (kept separate from money);
  * periods          -> a canonical (year, quarter|None) key.

`values_match` combines a value string with its unit string, so "383,285" +
"USD millions" and "383.285" + "USD billions" both reduce to 383285000000.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_SCALE_WORDS = {
    "thousand": Decimal(1_000),
    "thousands": Decimal(1_000),
    "k": Decimal(1_000),
    "million": Decimal(1_000_000),
    "millions": Decimal(1_000_000),
    "mm": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "m": Decimal(1_000_000),
    "billion": Decimal(1_000_000_000),
    "billions": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "b": Decimal(1_000_000_000),
    "trillion": Decimal(1_000_000_000_000),
    "trillions": Decimal(1_000_000_000_000),
}

_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-zA-Z%]+")


def _scale_from_words(text: str) -> Decimal:
    scale = Decimal(1)
    for w in _WORD_RE.findall(text.lower()):
        if w in _SCALE_WORDS:
            scale *= _SCALE_WORDS[w]
    return scale


def is_percent(unit: str | None, value: str | None) -> bool:
    blob = f"{unit or ''} {value or ''}".lower()
    return "percent" in blob or "%" in blob


def parse_number(text: str) -> Decimal | None:
    """Parse a numeric magnitude from free text, honoring parentheses as
    negative and inline scale words (e.g. "383.285 billion")."""
    if text is None:
        return None
    s = text.strip()
    if not s:
        return None
    # Strip a leading currency symbol so "$(1,234)" is recognized as negative.
    s = re.sub(r"^[$€£¥]\s*", "", s).strip()
    negative = False
    # Accounting negatives: (1,234), $(1,234), and — crucially — scaled forms
    # like "(42) million" where a scale word trails the closing paren. Match the
    # parenthesized magnitude independently of any suffix so the sign is never
    # dropped when a unit word follows.
    paren = re.match(r"\(\s*([\d,]+(?:\.\d+)?)\s*\)(.*)$", s)
    if paren:
        negative = True
        s = f"{paren.group(1)}{paren.group(2)}"
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        num = Decimal(m.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    if "-" in m.group(0):
        negative = True
        num = abs(num)
    num *= _scale_from_words(s)
    return -num if negative else num


def to_base(value: str | None, unit: str | None) -> Decimal | None:
    """Canonical magnitude: whole-dollar Decimal for money, plain number for
    percent. Scale is taken from exactly one source: if the value text already
    carries an inline scale word (e.g. "383,285 million"), the unit scale is NOT
    re-applied, otherwise the magnitude would be multiplied twice."""
    if value is None:
        return None
    base = parse_number(value)
    if base is None:
        return None
    if is_percent(unit, value):
        return base  # percentage points; no monetary scaling
    if _scale_from_words(value) == 1:
        base *= _scale_from_words(unit or "")
    return base


def values_match(
    v1: str | None, u1: str | None, v2: str | None, u2: str | None, rel_tol: str = "0.005"
) -> bool:
    """True if (value,unit) pairs denote the same magnitude within rel_tol.

    A small relative tolerance absorbs rounding (e.g. filings rounding to the
    nearest million vs. a model echoing 3 decimals of billions)."""
    a, b = to_base(v1, u1), to_base(v2, u2)
    if a is None or b is None:
        return False
    # percent-vs-money mismatch is never a match
    if is_percent(u1, v1) != is_percent(u2, v2):
        return False
    if a == b:
        return True
    denom = max(abs(a), abs(b))
    if denom == 0:
        return a == b
    return abs(a - b) / denom <= Decimal(rel_tol)


_PERIOD_Q = re.compile(r"\bq([1-4])\b", re.IGNORECASE)
_PERIOD_Y = re.compile(r"(19|20)\d{2}")


def canonical_period(text: str | None) -> tuple[int, int | None] | None:
    """Reduce a period label to (year, quarter|None). Handles 'FY2023',
    'fiscal 2023', 'Q2 2024', 'year ended September 30, 2023'."""
    if not text:
        return None
    qmatch = _PERIOD_Q.search(text)
    ymatch = _PERIOD_Y.search(text)
    if not ymatch:
        return None
    year = int(ymatch.group(0))
    quarter = int(qmatch.group(1)) if qmatch else None
    return (year, quarter)


def periods_match(p1: str | None, p2: str | None) -> bool:
    c1, c2 = canonical_period(p1), canonical_period(p2)
    return c1 is not None and c1 == c2
