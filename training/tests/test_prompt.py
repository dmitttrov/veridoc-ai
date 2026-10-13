from veridoc_ft.prompt import build_messages


def test_messages_have_system_and_user_with_untrusted_framing() -> None:
    msgs = build_messages("What was revenue?", ["Acme revenue was 10.", "Distractor."])
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert "UNTRUSTED DATA" in msgs[0]["content"]
    assert "NEVER" in msgs[0]["content"]
    assert "JSON" in msgs[0]["content"]
    assert "[E1]" in msgs[1]["content"] and "[E2]" in msgs[1]["content"]
    assert "What was revenue?" in msgs[1]["content"]


def test_no_evidence_is_handled() -> None:
    msgs = build_messages("Q?", [])
    assert "no evidence provided" in msgs[1]["content"]
