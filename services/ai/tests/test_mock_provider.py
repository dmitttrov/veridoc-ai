from app.models import ChatRequest, CitationsEvent, DoneEvent, TokenEvent
from app.providers.mock import MockProvider, _tokenize


async def _collect(request: ChatRequest) -> list:
    provider = MockProvider(model_name="veridoc-mock-test", token_delay_s=0.0)
    return [event async for event in provider.stream_chat(request)]


async def test_stream_shape_tokens_then_citations_then_done() -> None:
    events = await _collect(ChatRequest(message="What was revenue?"))

    assert isinstance(events[0], TokenEvent)
    assert isinstance(events[-1], DoneEvent)
    assert any(isinstance(e, CitationsEvent) for e in events)

    # Exactly one terminal event, and it is last.
    terminals = [e for e in events if isinstance(e, DoneEvent)]
    assert len(terminals) == 1
    assert terminals[0].mock is True
    assert terminals[0].model == "veridoc-mock-test"


async def test_output_is_deterministic() -> None:
    req = ChatRequest(message="Compare FY2023 and FY2022.")
    first = await _collect(req)
    second = await _collect(req)

    first_text = "".join(e.text for e in first if isinstance(e, TokenEvent))
    second_text = "".join(e.text for e in second if isinstance(e, TokenEvent))

    assert first_text == second_text
    assert "[MOCK MODE]" in first_text
    # The mock must not invent concrete financial figures.
    assert "No real financial figures are invented" in first_text


async def test_token_count_matches_emitted_tokens() -> None:
    events = await _collect(ChatRequest(message="hello"))
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    done = next(e for e in events if isinstance(e, DoneEvent))
    assert done.token_count == len(token_events)


async def test_selected_documents_drive_citations() -> None:
    events = await _collect(
        ChatRequest(message="Summarize", documentIds=["doc-globex-q2-2024"])
    )
    citations_event = next(e for e in events if isinstance(e, CitationsEvent))
    assert [c.document_id for c in citations_event.citations] == ["doc-globex-q2-2024"]


def test_tokenize_roundtrips() -> None:
    text = "alpha beta  gamma"
    assert "".join(_tokenize(text)) == text
