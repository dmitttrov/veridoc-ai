"""On-camera demo: BASE Qwen3-0.6B vs the fine-tuned LoRA adapter-v2 on
structured financial-fact extraction. Prints a clean side-by-side per example.

Shows the two weaknesses the adapter was trained to fix (negative/parenthesized
values; near-synonym metric confusion -> abstain), on BOTH real SEC-derived
figures and FRESH held-out cases (new fictional companies never in training) so
the improvement is visibly a generalizing fix, not memorization.

Run on the GPU server:
  cd ~/veridoc-phase4b/training && . .venv/bin/activate
  CUDA_VISIBLE_DEVICES=0 HF_HOME=/data/models/huggingface python scripts/demo_adapter.py
"""
from __future__ import annotations

from veridoc_ft.config import TrainConfig
from veridoc_ft.infer import extract, load_model
from veridoc_ft.realeval.normalize import values_match

ADAPTER = "artifacts/adapter-v2"

# (tag, question, evidence, gold_value_or_None, gold_unit, source)
CASES = [
    ("real · positive",
     "What was Apple Inc.'s total revenue for FY2024?",
     ["For FY2024, Apple Inc. reported operating income of $123,216 million.",
      "For FY2024, Apple Inc. reported total revenue of $391,035 million."],
     "391,035", "USD millions", "SEC EDGAR XBRL"),
    ("real · NEGATIVE cash flow",
     "What was JPMorgan Chase & Co.'s net cash from operating activities for FY2024?",
     ["For FY2024, JPMorgan Chase & Co. reported net cash from operating "
      "activities of $(42,012) million."],
     "(42,012)", "USD millions", "SEC EDGAR XBRL"),
    ("real · NEAR-SYNONYM (must abstain)",
     "What were Walmart Inc.'s cash and cash equivalents at the end of FY2025?",
     ["For FY2025, Walmart Inc. reported net cash from operating activities of "
      "$36,443 million."],
     None, None, "SEC EDGAR XBRL (answer absent)"),
    ("FRESH · net LOSS (held-out company)",
     "What was Zephyr Mining Corp's net income for FY2023?",
     ["Zephyr Mining Corp reported a net loss of $(318) million for FY2023.",
      "Zephyr Mining Corp total revenue for FY2023 was $2.1 billion."],
     "(318)", "USD millions", "fresh, not in training"),
    ("FRESH · NEAR-SYNONYM (held-out, must abstain)",
     "What was Delta Robotics Inc's net cash from operating activities for FY2022?",
     ["Delta Robotics Inc held cash and cash equivalents of $455 million at the "
      "end of FY2022."],
     None, None, "fresh, not in training"),
]


def _verdict(gold_val, gold_unit, result) -> str:
    if result is None:
        return "parse/schema FAIL"
    sup = result.get("supported")
    if gold_val is None:  # should abstain
        return "correct ABSTAIN" if not sup else "WRONG (answered)"
    if not sup:
        return "WRONG (abstained)"
    return "correct" if values_match(result.get("value"), result.get("unit"),
                                     gold_val, gold_unit) else "WRONG value"


def _fmt(result) -> str:
    if result is None:
        return "<no valid JSON>"
    if not result.get("supported"):
        return '{"supported": false}  (abstains)'
    return (f'{{"metric":"{result.get("metric")}", "value":"{result.get("value")}", '
            f'"unit":"{result.get("unit")}", "period":"{result.get("period")}", '
            f'"evidence":"{result.get("evidence")}"}}')


def main() -> None:
    cfg = TrainConfig()
    print("Loading BASE Qwen/Qwen3-0.6B @", cfg.model_revision[:12], "...", flush=True)
    base_m, base_t = load_model(cfg, None)
    print("Loading FINE-TUNED adapter-v2 (LoRA) ...", flush=True)
    ad_m, ad_t = load_model(cfg, ADAPTER)

    bar = "=" * 78
    base_ok = ad_ok = 0
    for i, (tag, q, ev, gv, gu, src) in enumerate(CASES, 1):
        print("\n" + bar)
        print(f"[{i}/{len(CASES)}]  {tag}   ({src})")
        print(f"Q: {q}")
        for marker, text in zip(("E1", "E2"), ev, strict=False):
            print(f"   [{marker}] {text}")
        b = extract(base_m, base_t, q, ev, cfg)
        a = extract(ad_m, ad_t, q, ev, cfg)
        bv, av = _verdict(gv, gu, b["result"]), _verdict(gv, gu, a["result"])
        base_ok += bv == "correct" or bv == "correct ABSTAIN"
        ad_ok += av == "correct" or av == "correct ABSTAIN"
        print(f"\n  BASE        -> {_fmt(b['result'])}")
        print(f"              => {bv}")
        print(f"  FINE-TUNED  -> {_fmt(a['result'])}")
        print(f"              => {av}")
    print("\n" + bar)
    print(f"SCORE on these {len(CASES)} cases:  base {base_ok}/{len(CASES)}   "
          f"fine-tuned {ad_ok}/{len(CASES)}")
    print(bar)


if __name__ == "__main__":
    main()
