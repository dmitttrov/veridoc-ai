"""Strict output schema for financial-fact extraction.

The model must emit JSON conforming to `ExtractionResult`. The schema forbids
extra keys and enforces the core invariant of a grounded extractor: an answer is
either SUPPORTED by a cited piece of evidence (value + evidence present) or it is
an explicit abstention (supported=False, value/unit/period/evidence all null).
This is what stops the model from inventing facts or evidence references.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, model_validator


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The metric that was asked about (echoed back, normalized).
    metric: str
    # The extracted value as written in the evidence, e.g. "482.6". Null when
    # the evidence does not support an answer.
    value: str | None = None
    # Unit / currency, e.g. "USD millions", "percent". Null when unsupported.
    unit: str | None = None
    # Reporting period, e.g. "FY2023", "Q2 2024". Null when unsupported.
    period: str | None = None
    # Evidence marker the value came from, e.g. "E1". Null when unsupported.
    evidence: str | None = None
    # Whether the evidence supports a concrete answer.
    supported: bool

    @model_validator(mode="after")
    def _check_invariant(self) -> ExtractionResult:
        if self.supported:
            if not (self.value or "").strip() or self.evidence is None:
                raise ValueError("supported=True requires a non-empty value and non-null evidence")
        else:
            if any(x is not None for x in (self.value, self.unit, self.period, self.evidence)):
                raise ValueError(
                    "supported=False requires value/unit/period/evidence to be null"
                )
        return self

    def to_json(self) -> str:
        # Compact, key-ordered JSON so training targets are deterministic.
        return json.dumps(self.model_dump(), separators=(",", ":"), sort_keys=True)


def schema_prompt_block() -> str:
    """A concise, human-readable schema description injected into the prompt."""
    return (
        "{\n"
        '  "metric": string,            // the metric asked about\n'
        '  "value": string|null,        // value as written, e.g. "482.6"; null if unsupported\n'
        '  "unit": string|null,         // e.g. "USD millions", "percent"; null if unsupported\n'
        '  "period": string|null,       // e.g. "FY2023"; null if unsupported\n'
        '  "evidence": string|null,     // evidence marker, e.g. "E1"; null if unsupported\n'
        '  "supported": boolean         // true only if an evidence passage supports the value\n'
        "}"
    )


def parse_extraction(text: str) -> tuple[ExtractionResult | None, str]:
    """Parse the first JSON object out of model text.

    Returns (result, status) where status is one of:
    "ok", "no_json", "invalid_json", "schema_invalid".

    Scans each '{' with a balanced-object decoder and returns the first object
    that decodes, so a valid object followed by trailing text containing braces
    (a second object, a code fence, chat-template residue) still parses.
    """
    idx = text.find("{")
    if idx == -1:
        return None, "no_json"
    decoder = json.JSONDecoder()
    data = None
    while idx != -1:
        try:
            data, _ = decoder.raw_decode(text, idx)
            break
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
    if data is None:
        return None, "invalid_json"
    try:
        return ExtractionResult.model_validate(data), "ok"
    except Exception:
        return None, "schema_invalid"
