from app.ingestion.chunk import chunk_page_text


def test_empty_page_yields_no_chunks() -> None:
    assert chunk_page_text("") == []
    assert chunk_page_text("   \n  ") == []


def test_short_page_is_single_chunk() -> None:
    chunks = chunk_page_text("short financial text", size=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0].char_start == 0
    assert chunks[0].text == "short financial text"


def test_chunk_text_equals_offset_slice() -> None:
    text = " ".join(f"token{i}" for i in range(200))
    for c in chunk_page_text(text, size=120, overlap=30):
        assert c.text == text[c.char_start : c.char_end]


def test_boundaries_do_not_split_words() -> None:
    text = " ".join(f"word{i}" for i in range(100))
    for c in chunk_page_text(text, size=90, overlap=20):
        assert not c.text.startswith(" ") and not c.text.endswith(" ")
        # A chunk never begins or ends mid-token.
        assert c.text.split()[0].startswith("word")


def test_offsets_and_indices_are_deterministic() -> None:
    text = " ".join(f"w{i}" for i in range(300))
    a = chunk_page_text(text, size=100, overlap=25)
    b = chunk_page_text(text, size=100, overlap=25)
    assert [(c.index, c.char_start, c.char_end) for c in a] == [
        (c.index, c.char_start, c.char_end) for c in b
    ]
    # Indices are contiguous from zero.
    assert [c.index for c in a] == list(range(len(a)))


def test_overlap_creates_shared_span() -> None:
    text = " ".join(f"w{i}" for i in range(300))
    chunks = chunk_page_text(text, size=100, overlap=40)
    assert len(chunks) >= 2
    # Each subsequent chunk starts before the previous one ended (overlap).
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        assert nxt.char_start < prev.char_end
        assert nxt.char_start > prev.char_start
