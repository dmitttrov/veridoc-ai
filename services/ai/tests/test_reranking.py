import pytest

from app.config import Settings
from app.reranking import build_reranker
from app.reranking.deterministic import DeterministicReranker


def test_deterministic_scores_are_reproducible() -> None:
    r = DeterministicReranker()
    passages = ["research and development expenses rose", "the weather was sunny today"]
    a = r.score("research and development", passages)
    b = r.score("research and development", passages)
    assert a == b
    # The on-topic passage scores higher.
    assert a[0] > a[1]


def test_deterministic_reranker_reorders_relevant_first() -> None:
    r = DeterministicReranker()
    passages = [
        "unrelated boilerplate about the company history",
        "total revenue for fiscal 2023 was 482.6 million dollars",
    ]
    scores = r.score("what was total revenue in 2023", passages)
    assert scores[1] > scores[0]


def test_empty_query_scores_zero() -> None:
    r = DeterministicReranker()
    assert r.score("the of and", ["anything here"]) == [0.0]


def test_factory_none_returns_none() -> None:
    assert build_reranker(Settings(reranker_provider="none")) is None


def test_factory_deterministic() -> None:
    r = build_reranker(Settings(reranker_provider="deterministic"))
    assert r is not None
    assert r.model_id == "veridoc-deterministic-reranker-v1"


def test_factory_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        build_reranker(Settings(reranker_provider="bogus"))


def test_factory_cross_encoder_unavailable_falls_back(monkeypatch) -> None:
    # Simulate the real reranker being unavailable: the factory must return
    # None (explicit fallback), never raise and never silently pretend.
    import app.reranking.cross_encoder as ce

    def _boom(model_name: str):
        raise RuntimeError("weights not available")

    monkeypatch.setattr(ce, "CrossEncoderReranker", _boom, raising=True)
    assert build_reranker(Settings(reranker_provider="cross-encoder")) is None
