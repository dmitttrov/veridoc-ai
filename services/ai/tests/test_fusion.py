from app.retrieval.service import reciprocal_rank_fusion


def test_rrf_rewards_agreement_across_lists() -> None:
    lexical = ["a", "b", "c"]
    semantic = ["b", "a", "d"]
    scores = reciprocal_rank_fusion([lexical, semantic])
    # 'b' is rank 2 lexically but rank 1 semantically; 'a' is rank 1 then 2.
    # Both appear in both lists, so they outrank single-list items.
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["d"]


def test_rrf_single_list_follows_rank_order() -> None:
    scores = reciprocal_rank_fusion([["x", "y", "z"]])
    assert scores["x"] > scores["y"] > scores["z"]


def test_rrf_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == {}


def test_rrf_k_controls_contribution() -> None:
    small_k = reciprocal_rank_fusion([["a"]], k=1)["a"]
    large_k = reciprocal_rank_fusion([["a"]], k=1000)["a"]
    assert small_k > large_k
