from app.ingestion.normalize import normalize_text


def test_normalizes_line_endings_and_whitespace() -> None:
    assert normalize_text("a  b\r\n\r\n\r\nc  \n") == "a b\n\nc"


def test_is_idempotent() -> None:
    once = normalize_text("Revenue\twas 482.6   million\r\n\r\n\r\n")
    twice = normalize_text(once)
    assert once == twice


def test_strips_control_characters_but_keeps_newline_tab() -> None:
    raw = "line1\x00\x07\nline2"
    out = normalize_text(raw)
    assert "\x00" not in out and "\x07" not in out
    assert out == "line1\nline2"


def test_empty_and_whitespace_only() -> None:
    assert normalize_text("") == ""
    assert normalize_text("   \n\t  \n ") == ""
