"""Real-world evaluation (oracle-evidence) of base vs adapter.

Oracle mode (Step 3A): the human-verified correct passage is included in the
evidence, so this isolates the model's EXTRACTION ability from retrieval. Value
comparison uses the financial normalizer (millions/billions, parentheses,
currency), so "391,035"/"USD millions" matches the raw figure.

Citation VALIDITY (marker is one of the provided passages) is reported
separately from citation SUPPORT (the cited passage actually contains the gold
value) — a valid citation does not prove support.

End-to-end RAG mode (Step 3B) is intentionally NOT implemented here: it requires
the services/ai hybrid-retrieval stack (Postgres+pgvector) over ingested real
documents to supply the evidence, then feeds those passages through this same
scorer. See docs/EVALUATION.md for how to wire it; it is out of scope until the
retrieval stack is stood up with the real documents.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from veridoc_ft.config import TrainConfig
from veridoc_ft.realeval.dataset import RealExample, load_real
from veridoc_ft.realeval.normalize import periods_match, to_base, values_match


def _passage_supports(evidence: list[str], marker: str | None, gold: dict) -> bool:
    """Does the cited passage actually contain the gold value? (support, not validity)"""
    if not marker or not marker.startswith("E"):
        return False
    try:
        idx = int(marker[1:]) - 1
    except ValueError:
        return False
    if not (0 <= idx < len(evidence)):
        return False
    passage = evidence[idx]
    if to_base(gold.get("value"), gold.get("unit")) is None:
        return False
    # Scan the passage for a number matching the gold magnitude. Each number is
    # read with ITS OWN inline scale word (million/billion/…) — not the gold
    # unit — so support is judged against the figure as written in the passage.
    import re
    num_re = re.compile(
        r"\$?\(?-?[\d,]+(?:\.\d+)?\)?(?:\s*(?:million|billion|thousand|percent))?",
        re.IGNORECASE,
    )
    for m in num_re.findall(passage):
        if m.strip() and values_match(m, None, gold.get("value"), gold.get("unit")):
            return True
    return False


def score_real(ex: RealExample, pred: dict) -> dict:
    gold = ex.target
    status = pred["status"]
    result = pred["result"]
    schema_valid = status == "ok"
    markers = {f"E{i + 1}" for i in range(len(ex.evidence))}

    s: dict[str, Any] = {
        "id": ex.id,
        "category": ex.category,
        "company": ex.company,
        "json_parse": status in {"ok", "schema_invalid"},
        "schema_valid": schema_valid,
        "latency_s": pred["latency_s"],
        "gold_supported": bool(gold["supported"]),
        "pred_supported": bool(result["supported"]) if schema_valid else False,
    }

    if gold["supported"]:
        pv = result.get("value") if schema_valid else None
        pu = result.get("unit") if schema_valid else None
        s["value_exact"] = schema_valid and values_match(pv, pu, gold["value"], gold["unit"])
        s["unit_correct"] = schema_valid and (
            ("percent" in (pu or "").lower()) == ("percent" in (gold["unit"] or "").lower())
        )
        s["period_correct"] = schema_valid and periods_match(
            result.get("period"), gold.get("period")
        )
        s["metric_exact"] = schema_valid and (
            (result.get("metric") or "").strip().lower() == gold["metric"].strip().lower()
        )
        s["citation_valid"] = schema_valid and result.get("evidence") in markers
        s["citation_support"] = schema_valid and _passage_supports(
            ex.evidence, result.get("evidence"), gold
        )
    return s


def aggregate(scores: list[dict]) -> dict:
    n = len(scores)

    def rate(key: str, subset: list[dict]) -> float | None:
        vals = [bool(x[key]) for x in subset if key in x]
        return round(sum(vals) / len(vals), 4) if vals else None

    sup = [s for s in scores if s.get("gold_supported")]
    uns = [s for s in scores if s.get("gold_supported") is False]
    tp = sum(1 for s in uns if not s["pred_supported"])
    fn = sum(1 for s in uns if s["pred_supported"])
    fp = sum(1 for s in sup if not s["pred_supported"])
    return {
        "n": n,
        "json_parse_success": rate("json_parse", scores),
        "schema_valid": rate("schema_valid", scores),
        "metric_exact": rate("metric_exact", sup),
        "value_exact": rate("value_exact", sup),
        "unit_correct": rate("unit_correct", sup),
        "period_correct": rate("period_correct", sup),
        "citation_valid": rate("citation_valid", sup),
        "citation_support": rate("citation_support", sup),
        "abstention_precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "abstention_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "mean_latency_s": round(sum(s["latency_s"] for s in scores) / n, 4) if n else None,
        "n_supported": len(sup),
        "n_unsupported": len(uns),
    }


def evaluate_real(
    config: TrainConfig,
    data_path: str,
    adapter_path: str | None = None,
    limit: int | None = None,
    out_path: str | None = None,
) -> dict:
    from veridoc_ft.infer import extract, load_model  # lazy: needs torch + weights

    model, tokenizer = load_model(config, adapter_path)
    examples = load_real(data_path)
    if limit:
        examples = examples[:limit]
    scores, details = [], []
    for ex in examples:
        pred = extract(model, tokenizer, ex.question, ex.evidence, config)
        sc = score_real(ex, pred)
        scores.append(sc)
        details.append({**sc, "raw": pred["raw"][:400]})
    report = {
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "adapter": adapter_path,
        "mode": "oracle",
        "metrics": aggregate(scores),
        "details": details,
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Real-world oracle evaluation")
    ap.add_argument("--data", default="data/realeval/real_test.jsonl")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rep = evaluate_real(TrainConfig(), args.data, args.adapter, args.limit, args.out)
    print(json.dumps(rep["metrics"], indent=2))
