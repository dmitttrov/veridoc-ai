from veridoc_ft.evaluate import paired_bootstrap


def _scores(ids, vals, key="value_exact"):
    return [{"id": i, key: v} for i, v in zip(ids, vals, strict=True)]


def test_strict_improvement_is_credible() -> None:
    ids = [f"e{i}" for i in range(20)]
    base = _scores(ids, [False] * 20)
    adapter = _scores(ids, [True] * 20)
    r = paired_bootstrap(base, adapter, "value_exact", n_boot=2000, seed=0)
    assert r is not None
    assert r["mean_diff"] == 1.0
    assert r["ci95"][0] > 0 and r["credible"] is True


def test_no_difference_not_credible() -> None:
    ids = [f"e{i}" for i in range(20)]
    vals = [True, False] * 10
    r = paired_bootstrap(_scores(ids, vals), _scores(ids, vals), "value_exact", n_boot=2000)
    assert r["mean_diff"] == 0.0
    assert r["credible"] is False


def test_aligns_by_id_regardless_of_order() -> None:
    base = _scores(["a", "b", "c"], [False, False, False])
    adapter = list(reversed(_scores(["a", "b", "c"], [True, True, True])))
    r = paired_bootstrap(base, adapter, "value_exact", n_boot=500)
    assert r["n"] == 3 and r["mean_diff"] == 1.0


def test_deterministic() -> None:
    ids = [f"e{i}" for i in range(15)]
    base = _scores(ids, [i % 2 == 0 for i in range(15)])
    adapter = _scores(ids, [True] * 15)
    a = paired_bootstrap(base, adapter, "value_exact", n_boot=1000, seed=7)
    b = paired_bootstrap(base, adapter, "value_exact", n_boot=1000, seed=7)
    assert a == b
