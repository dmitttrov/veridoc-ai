from veridoc_ft.dataset_v2 import V2_COMPANIES, build, generate_v2_examples
from veridoc_ft.realeval.dataset import COMPANIES as SEC_COMPANIES
from veridoc_ft.realeval.dataset import marker_for
from veridoc_ft.schema import ExtractionResult


def test_v2_targets_negatives_and_synonyms() -> None:
    ex = generate_v2_examples()
    # negative/parenthesized gold values exist
    negs = [e for e in ex if e.target.get("value") and e.target["value"].startswith("(")]
    assert negs, "expected parenthesized negative values"
    # near-synonym abstention examples exist for both cash metrics
    syn_abstain = [e for e in ex if e.category == "unanswerable"
                   and e.target["metric"] in
                   ("cash and cash equivalents", "net cash from operating activities")]
    assert len(syn_abstain) >= 2
    # all examples validate against the schema + cited markers
    for e in ex:
        r = ExtractionResult.model_validate(e.target)
        if r.supported:
            assert r.evidence in {marker_for(i) for i in range(len(e.evidence))}


def test_v2_seed_changes_generated_values() -> None:
    # Regression: the v2 half must honor --seed (previously ignored).
    a = generate_v2_examples(1)
    b = generate_v2_examples(2)
    assert [e.id for e in a] == [e.id for e in b]  # structure stable
    assert any(x.target != y.target for x, y in zip(a, b, strict=True))  # values differ


def test_v2_restatement_changes_the_figure() -> None:
    # Regression: a "conflicting" restatement must not restate to the same value.
    for e in generate_v2_examples():
        if e.category == "conflicting":
            assert e.evidence[0] != e.evidence[1]


def test_v2_disjoint_from_sec_benchmark() -> None:
    sec = {c[0] for c in SEC_COMPANIES}
    assert set(V2_COMPANIES).isdisjoint(sec)  # no company overlap with frozen eval


def test_v2_build_deterministic_and_split_clean(tmp_path) -> None:
    a = build(str(tmp_path / "a"))
    b = build(str(tmp_path / "b"))
    assert a["sha256"] == b["sha256"]
    train = set(a["families"]["train"])
    val = set(a["families"]["val"])
    test = set(a["families"]["test"])
    assert train and test
    assert train.isdisjoint(val) and train.isdisjoint(test) and val.isdisjoint(test)
    # v2 strictly extends v1 (more examples than v1's 288)
    assert sum(a["counts"].values()) > 288
