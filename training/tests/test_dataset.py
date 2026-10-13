from veridoc_ft.dataset import build, generate_examples, load_split, validate_example


def test_examples_valid_and_cover_categories() -> None:
    examples = generate_examples(seed=123)
    for ex in examples:
        validate_example(ex)
    cats = {ex.category for ex in examples}
    assert {"answerable", "unanswerable", "conflicting", "injection"} <= cats


def test_build_is_deterministic(tmp_path) -> None:
    a = build(str(tmp_path / "a"), seed=123)
    b = build(str(tmp_path / "b"), seed=123)
    assert a["sha256"] == b["sha256"]  # byte-identical splits
    assert a["counts"] == b["counts"]


def test_splits_have_no_family_leakage(tmp_path) -> None:
    m = build(str(tmp_path / "d"), seed=123)
    train = set(m["families"]["train"])
    val = set(m["families"]["val"])
    test = set(m["families"]["test"])
    assert train and test  # non-empty
    assert train.isdisjoint(val)
    assert train.isdisjoint(test)
    assert val.isdisjoint(test)


def test_dedup_removes_duplicates(tmp_path) -> None:
    m = build(str(tmp_path / "d"), seed=123)
    total = sum(m["counts"].values())
    # Re-load and check ids are unique across splits.
    ids = []
    for split in ("train", "val", "test"):
        ids += [ex.id for ex in load_split(str(tmp_path / "d"), split)]
    assert len(ids) == len(set(ids)) == total


def test_manifest_records_version_and_hashes(tmp_path) -> None:
    m = build(str(tmp_path / "d"), seed=123)
    assert m["version"] == "v1"
    assert set(m["sha256"]) == {"train", "val", "test"}
    assert all(len(h) == 64 for h in m["sha256"].values())
