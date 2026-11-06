"""Unit tests for conversational grounded RAG: deterministic query
condensation, history-aware prompt assembly, and the service wiring that
connects them (no database required)."""
from __future__ import annotations

from app.config import Settings
from app.models import (
    ChatMessage,
    RetrievalResponse,
    RetrievalScores,
    RetrievedPassage,
)
from app.providers.base import ChatMessage as ProviderMessage
from app.providers.base import GenerationResult
from app.providers.mock import MockProvider
from app.rag.condense import MAX_QUERY_CHARS, condense_query
from app.rag.prompt import build_messages
from app.rag.service import answer_question


def _passage(index: int, text: str) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=f"00000000-0000-0000-0000-00000000000{index}",
        document_id="11111111-1111-1111-1111-111111111111",
        document_title="Acme FY2023",
        page=index + 1,
        text=text,
        char_start=0,
        char_end=len(text),
        scores=RetrievalScores(lexical=0.0, semantic=0.0, fused=0.0),
        citation="Acme FY2023, p.1",
    )


PASSAGES = [_passage(0, "Revenue was 482.6 million."), _passage(1, "R&D was 92.4 million.")]


def _user(content: str) -> ChatMessage:
    return ChatMessage(role="user", content=content)


def _assistant(content: str) -> ChatMessage:
    return ChatMessage(role="assistant", content=content)


# --- condense_query ---------------------------------------------------------


def test_question_alone_is_the_query() -> None:
    assert condense_query("What was revenue?", []) == "What was revenue?"


def test_follow_up_pulls_recent_user_turns() -> None:
    history = [
        _user("What was total revenue in FY2023?"),
        _assistant("Revenue was 482.6 million [E1]."),
    ]
    query = condense_query("What about 2022?", history)
    assert query.startswith("What about 2022?")
    assert "total revenue in FY2023" in query


def test_assistant_turns_are_excluded_from_the_query() -> None:
    history = [_assistant("Revenue was 482.6 million [E1].")]
    assert condense_query("What about 2022?", history) == "What about 2022?"


def test_newest_user_turns_win_and_count_is_bounded() -> None:
    history = [_user(f"question number {i}") for i in range(10)]
    query = condense_query("follow-up?", history)
    # The 4 most recent user turns are folded in, newest first.
    assert "question number 9" in query
    assert "question number 6" in query
    assert "question number 5" not in query


def test_query_never_exceeds_the_retrieval_contract_bound() -> None:
    history = [_user("x" * 1900)]
    query = condense_query("y" * 1900, history)
    assert len(query) <= MAX_QUERY_CHARS
    # The question itself always survives; history that would overflow is dropped.
    assert query.startswith("y" * 1900)


def test_whitespace_only_history_turns_are_skipped() -> None:
    assert condense_query("q?", [_user("   ")]) == "q?"


# --- prompt history ---------------------------------------------------------


def test_history_sits_between_system_and_final_user_message() -> None:
    history = [_user("What was revenue?"), _assistant("Revenue was 482.6 million [E1].")]
    messages = build_messages("What about R&D?", PASSAGES, history)
    assert [m.role for m in messages] == ["system", "user", "assistant", "user"]
    # The final user message still carries the question + evidence block.
    assert "What about R&D?" in messages[-1].content
    assert "[E1]" in messages[-1].content


def test_prior_assistant_markers_are_stripped_from_history() -> None:
    # Markers in an old answer referred to a PREVIOUS retrieval; replaying them
    # against the current passage numbering would mis-attribute evidence.
    history = [_assistant("Revenue was 482.6 million [E1] [E2].")]
    messages = build_messages("q?", PASSAGES, history)
    assistant = next(m for m in messages if m.role == "assistant")
    assert "[E1]" not in assistant.content
    assert "Revenue was 482.6 million" in assistant.content


def test_history_turns_are_truncated_and_capped() -> None:
    history = [_user(f"turn {i} " + "x" * 5000) for i in range(12)]
    messages = build_messages("q?", PASSAGES, history)
    history_msgs = messages[1:-1]
    assert len(history_msgs) == 8  # most recent 8 of 12
    assert all(len(m.content) <= 1501 for m in history_msgs)  # 1500 + ellipsis
    assert "turn 11" in history_msgs[-1].content


def test_no_history_keeps_the_original_two_message_shape() -> None:
    messages = build_messages("q?", PASSAGES)
    assert [m.role for m in messages] == ["system", "user"]


def test_system_prompt_forbids_citing_history() -> None:
    system = build_messages("q?", PASSAGES, [_user("earlier")])[0].content
    assert "NOT evidence" in system


# --- service wiring (run_retrieve faked; no DB) ------------------------------


class _RecordingProvider:
    """Captures the exact messages handed to generate()."""

    name = "recorder"
    is_mock = False

    def __init__(self) -> None:
        self.messages: list[ProviderMessage] = []

    async def generate(self, messages, *, max_tokens, temperature):
        self.messages = list(messages)
        return GenerationResult(text="Grounded [E1].", model=self.name, token_count=2)

    def stream_chat(self, request):  # pragma: no cover - unused here
        raise NotImplementedError


def _fake_retrieve(captured: dict):
    async def fake(pool, embedder, request, reranker, *, rerank_candidate_k, expand_queries=False):
        captured["query"] = request.query
        return RetrievalResponse(
            query=request.query,
            passages=PASSAGES,
            embedding_model="veridoc-deterministic-emb-v1",
            embedding_dim=384,
        )

    return fake


async def test_answer_question_condenses_history_into_retrieval_query(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr("app.rag.service.run_retrieve", _fake_retrieve(captured))
    provider = _RecordingProvider()

    history = [
        _user("What was total revenue in FY2023?"),
        _assistant("Revenue was 482.6 million [E1]."),
    ]
    outcome = await answer_question(
        None, None, None, provider, Settings(),
        question="What about R&D?", document_ids=[], top_k=5, rerank=None,
        history=history,
    )

    # Retrieval saw the condensed standalone query, not the bare follow-up.
    assert captured["query"].startswith("What about R&D?")
    assert "total revenue in FY2023" in captured["query"]
    # The provider saw the bounded conversation plus the evidence message.
    assert [m.role for m in provider.messages] == ["system", "user", "assistant", "user"]
    # And the verified pipeline still produced a traceable citation.
    assert outcome.abstained is False
    assert [c.marker for c in outcome.citations] == ["E1"]


async def test_mock_provider_still_grounds_with_history_present(monkeypatch) -> None:
    # The mock reads markers from the LAST user message; history user turns
    # must not shadow the evidence-bearing final message.
    captured: dict = {}
    monkeypatch.setattr("app.rag.service.run_retrieve", _fake_retrieve(captured))
    provider = MockProvider(model_name="veridoc-mock-0.1")

    outcome = await answer_question(
        None, None, None, provider, Settings(),
        question="What about R&D?", document_ids=[], top_k=5, rerank=None,
        history=[_user("What was revenue?"), _assistant("482.6 million [E1].")],
    )
    assert outcome.abstained is False
    assert outcome.citations, "mock should cite current-turn evidence markers"
    assert outcome.invalid_citation_count == 0
