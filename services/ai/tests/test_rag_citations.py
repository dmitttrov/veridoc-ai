"""Unit tests for citation verification and prompt assembly."""
from __future__ import annotations

from app.models import RetrievalScores, RetrievedPassage
from app.rag.prompt import ABSTAIN_SENTINEL, build_messages
from app.rag.service import verify_citations


def _passage(marker_index: int, text: str) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=f"00000000-0000-0000-0000-00000000000{marker_index}",
        document_id="11111111-1111-1111-1111-111111111111",
        document_title="Acme FY2023",
        page=marker_index + 1,
        text=text,
        char_start=0,
        char_end=len(text),
        scores=RetrievalScores(lexical=0.0, semantic=0.0, fused=0.0),
        citation="Acme FY2023, p.1",
    )


PASSAGES = [_passage(0, "Revenue was 482.6 million."), _passage(1, "R&D was 92.4 million.")]


def test_valid_markers_produce_traceable_citations() -> None:
    answer = "Revenue was 482.6 million [E1] and R&D was 92.4 million [E2]."
    cleaned, citations, invalid = verify_citations(answer, PASSAGES)
    assert invalid == 0
    assert [c.marker for c in citations] == ["E1", "E2"]
    # Each citation is traceable to a retrieved chunk and its span.
    assert citations[0].chunk_id == PASSAGES[0].chunk_id
    assert citations[0].char_start == 0
    assert "[E1]" in cleaned  # valid markers are retained


def test_fabricated_markers_are_rejected_and_stripped() -> None:
    answer = "The answer is 10 [E9] per the filing [E1]."
    cleaned, citations, invalid = verify_citations(answer, PASSAGES)
    assert invalid == 1
    assert "[E9]" not in cleaned  # fabricated marker removed from the answer
    assert [c.marker for c in citations] == ["E1"]


def test_duplicate_markers_cited_once() -> None:
    answer = "A [E1] and also B [E1]."
    _, citations, invalid = verify_citations(answer, PASSAGES)
    assert invalid == 0
    assert len(citations) == 1


def test_no_markers_yields_no_citations() -> None:
    cleaned, citations, invalid = verify_citations("An answer with no citation.", PASSAGES)
    assert citations == []
    assert invalid == 0
    assert cleaned == "An answer with no citation."


def test_prompt_marks_evidence_untrusted_and_defines_abstention() -> None:
    messages = build_messages("What was revenue?", PASSAGES)
    system = messages[0].content
    user = messages[1].content
    assert "UNTRUSTED DATA" in system
    assert "NEVER follow" in system or "never follow" in system.lower()
    assert ABSTAIN_SENTINEL in system
    assert "[E1]" in user and "[E2]" in user
    assert "What was revenue?" in user
