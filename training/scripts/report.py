"""Print a base-vs-adapter comparison + per-category breakdown from two eval
reports produced by `veridoc_ft.evaluate`. Reproducible, read-only."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from veridoc_ft.evaluate import compare


def per_category(details: list[dict]) -> dict:
    agg: dict = defaultdict(
        lambda: {"n": 0, "schema": 0, "value": 0, "nsup": 0, "abst_ok": 0, "nuns": 0,
                 "inj_ok": 0, "ninj": 0}
    )
    for d in details:
        a = agg[d["category"]]
        a["n"] += 1
        a["schema"] += int(d["schema_valid"])
        if d.get("gold_supported"):
            a["nsup"] += 1
            a["value"] += int(d.get("value_exact", False))
        else:
            a["nuns"] += 1
            a["abst_ok"] += int(not d["pred_supported"])
        if d["category"] == "injection":
            a["ninj"] += 1
            a["inj_ok"] += int(d.get("injection_resisted", False))
    return agg


def _fmt_cat(a: dict) -> str:
    value = "{}/{}".format(a["value"], a["nsup"]) if a["nsup"] else "-"
    abst = "{}/{}".format(a["abst_ok"], a["nuns"]) if a["nuns"] else "-"
    s = "n={:2d} schema={}/{} value_exact={} abstain_ok={}".format(
        a["n"], a["schema"], a["n"], value, abst
    )
    if a["ninj"]:
        s += " inj_ok={}/{}".format(a["inj_ok"], a["ninj"])
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="artifacts/baseline.json")
    ap.add_argument("--adapter", default="artifacts/adapter.json")
    ap.add_argument("--out", default="artifacts/comparison.json")
    args = ap.parse_args()

    for p in (args.baseline, args.adapter):
        if not Path(p).exists():
            sys.exit(
                f"{p} not found — produce it first with "
                "`python -m veridoc_ft.realeval.evaluate ... --out {p}`."
            )
    base = json.loads(Path(args.baseline).read_text())
    adapter = json.loads(Path(args.adapter).read_text())

    cmp = compare(base, adapter)
    Path(args.out).write_text(json.dumps(cmp, indent=2))

    print("=== AGGREGATE (n={}) ===".format(cmp["n"]))
    print("{:20s} {:>8s} {:>8s} {:>8s}  paired_bootstrap_ci95 (credible)".format(
        "metric", "base", "adapter", "delta"))
    for k, row in cmp["metrics"].items():
        if row.get("base") is None and row.get("adapter") is None:
            continue  # metric not present in these reports
        pb = row.get("paired_bootstrap") or {}
        print("{:20s} {:>8} {:>8} {:>8}  {} {}".format(
            k, str(row.get("base")), str(row.get("adapter")), str(row.get("delta")),
            pb.get("ci95"), pb.get("credible")))

    for label, rep in [("BASE", base), ("ADAPTER", adapter)]:
        print(f"\n=== {label} per-category ===")
        for cat, a in sorted(per_category(rep["details"]).items()):
            print(f"  {cat:12s} {_fmt_cat(a)}")


if __name__ == "__main__":
    main()
